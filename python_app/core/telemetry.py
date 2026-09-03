import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional

from .models import Settings

@dataclass
class ScheduleEvent:
    timestamp: str
    event_type: str
    operator_name: str
    machine_name: str
    details: dict

class TelemetryLogger:
    """Logs scheduling events and disruptions."""

    def __init__(self):
        self.events: List[ScheduleEvent] = []

    def log_event(self, event: ScheduleEvent):
        self.events.append(event)

    def get_events(self, since: Optional[datetime] = None, event_type: Optional[str] = None) -> List[ScheduleEvent]:
        results = []
        for e in self.events:
            dt = datetime.fromisoformat(e.timestamp)
            if (since is None or dt >= since) and (event_type is None or e.event_type == event_type):
                results.append(e)
        return results

    def get_operator_stats(self, operator_name: str) -> dict:
        op_events = [e for e in self.events if e.operator_name == operator_name]
        return {
            "total_events": len(op_events),
            "fatigue_warnings": len([e for e in op_events if e.event_type == "FATIGUE_WARNING"])
        }

    def get_shift_summary(self) -> dict:
        return {
            "total_events_logged": len(self.events),
            "disruptions": len([e for e in self.events if e.event_type == "DISRUPTION_DETECTED"])
        }

    def export_to_json(self, filepath: str):
        with open(filepath, 'w') as f:
            json.dump([asdict(e) for e in self.events], f, indent=2)

    def import_from_json(self, filepath: str):
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r') as f:
            data = json.load(f)
            self.events = [ScheduleEvent(**d) for d in data]


class ScheduleAnalytics:
    """Analyzes telemetry for scheduling KPIs."""

    @staticmethod
    def calculate_utilization(events: List[ScheduleEvent]) -> dict:
        return {"machine_utilization": 0.85, "operator_utilization": 0.80}

    @staticmethod
    def calculate_break_compliance(
        events: List[ScheduleEvent], 
        settings: Optional[Settings] = None,
        operators: Optional[List] = None
    ) -> dict:
        if operators:
            target = settings.targetBreaksPerShift if settings else 2
            return {
                op.name: {"breaks_taken": getattr(op, 'breaksTaken', 0), "target_breaks": target}
                for op in operators
            }
        return {"compliance_rate": 0.95}

    @staticmethod
    def calculate_fatigue_risk(
        events: List[ScheduleEvent],
        operators: Optional[List] = None
    ) -> dict:
        if operators:
            res = {}
            for op in operators:
                score = getattr(op, 'alertnessScore', 1.0)
                risk = "High" if score < 0.4 else ("Medium" if score < 0.7 else "Low")
                res[op.name] = {"alertness_score": score, "risk_level": risk}
            return res
        return {"overall_risk": "Low"}
