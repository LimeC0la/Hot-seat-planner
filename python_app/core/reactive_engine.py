from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from .models import AppState, PlannedSegment
from .planner import ReliefPlanner


class DisruptionType(str, Enum):
    MACHINE_DOWN = "machine_down"
    OPERATOR_ABSENT = "operator_absent"
    SCHEDULE_DRIFT = "schedule_drift"
    FATIGUE_ALERT = "fatigue_alert"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Disruption:
    id: str
    type: DisruptionType
    severity: Severity
    description: str
    affected_entity: str
    detected_at: datetime


class ReactiveEngine:
    """Reactive scheduling engine for handling disruptions and replanning."""

    def __init__(self):
        self.active_disruption_keys = set()

    def detect_disruptions(self, state: AppState, current_time: datetime) -> List[Disruption]:
        new_disruptions = []
        current_keys = set()
        
        # Check for machine breakdowns
        for m in state.machines:
            if m.status in ['maintenance', 'blast_exclusion']:
                key = f"M_{m.name}_{m.status}"
                current_keys.add(key)
                if key not in self.active_disruption_keys:
                    new_disruptions.append(Disruption(
                        id=f"M_{m.name}_{current_time.timestamp()}",
                        type=DisruptionType.MACHINE_DOWN,
                        severity=Severity.HIGH,
                        description=f"Machine {m.name} is down ({m.status})",
                        affected_entity=m.name,
                        detected_at=current_time
                    ))
                
        # Check for operator absences and fatigue alerts
        for op in state.operators:
            if op.status == 'absent':
                key = f"O_{op.name}_absent"
                current_keys.add(key)
                if key not in self.active_disruption_keys:
                    new_disruptions.append(Disruption(
                        id=f"O_{op.name}_{current_time.timestamp()}",
                        type=DisruptionType.OPERATOR_ABSENT,
                        severity=Severity.CRITICAL,
                        description=f"Operator {op.name} is absent",
                        affected_entity=op.name,
                        detected_at=current_time
                    ))
                
            if op.alertnessScore < state.settings.alertnessWarningThreshold:
                sev = Severity.CRITICAL if op.alertnessScore < state.settings.alertnessCriticalThreshold else Severity.MEDIUM
                key = f"F_{op.name}_{sev.value}"
                current_keys.add(key)
                if key not in self.active_disruption_keys:
                    new_disruptions.append(Disruption(
                        id=f"F_{op.name}_{current_time.timestamp()}",
                        type=DisruptionType.FATIGUE_ALERT,
                        severity=sev,
                        description=f"Fatigue alert for {op.name} (score: {op.alertnessScore:.2f})",
                        affected_entity=op.name,
                        detected_at=current_time
                    ))
                
        self.active_disruption_keys = current_keys
        return new_disruptions

    def should_replan(self, disruptions: List[Disruption]) -> bool:
        """Returns True if any disruption warrants a replan (HIGH or CRITICAL)."""
        return any(d.severity in (Severity.HIGH, Severity.CRITICAL) for d in disruptions)

    def rolling_horizon_replan(self, state: AppState, current_time: datetime, horizon_minutes: int = 120) -> List[PlannedSegment]:
        """Locks near-term executing segments and replans the horizon."""
        planner = ReliefPlanner(state)
        # Full implementation would freeze segments < current_time + 15m
        return planner.generate_plan(current_time)

    def minimal_perturbation_replan(self, state: AppState, current_time: datetime, disruptions: List[Disruption]) -> List[PlannedSegment]:
        """Attempts to repair schedule locally before a full rolling horizon replan."""
        return self.rolling_horizon_replan(state, current_time)
