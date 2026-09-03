from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4


# ──────────────────────────────────────────────────────────────
# Status Enums  (str, Enum keeps JSON serialization as strings)
# ──────────────────────────────────────────────────────────────

class OperatorStatus(str, Enum):
    """Possible states for an operator during a shift."""
    WORKING = "working"
    STANDBY = "standby"
    ON_BREAK = "on_break"
    ABSENT = "absent"
    FATIGUED = "fatigued"  # flagged by fatigue monitoring system

class MachineStatus(str, Enum):
    """Possible states for a machine."""
    OPERATIONAL = "operational"
    NOT_REQUIRED = "not_required"
    MAINTENANCE = "maintenance"
    BLAST_EXCLUSION = "blast_exclusion"
    SETUP = "setup"  # during changeover / setup window


# ──────────────────────────────────────────────────────────────
# Domain Models
# ──────────────────────────────────────────────────────────────

@dataclass
class Operator:
    name: str
    qualifications: List[str]
    id: str = ""
    status: str = 'standby'  # working, standby, on_break, absent, fatigued
    standbyTimeMinutes: int = 0
    breaksTaken: int = 0
    currentAssignmentId: Optional[str] = None
    # ── Phase 1: Competency multipliers (§2.1) ──
    # Maps machine type -> multiplier (1.0 = baseline, 0.7 = expert/fast, 1.5 = novice/slow)
    # If empty, all qualified types default to 1.0
    competencyMultipliers: Dict[str, float] = field(default_factory=dict)
    # ── Phase 1: Fatigue tracking (§4.2) ──
    cumulativeFatigueMinutes: float = 0.0        # accumulated work since last full rest
    consecutiveShiftsWorked: int = 0             # for consecutive shift limit enforcement
    lastFullRestEnd: Optional[str] = None        # ISO timestamp of last 48h+ reset
    alertnessScore: float = 1.0                  # 1.0 = fully alert, 0.0 = critical

    def __post_init__(self):
        if not self.id:
            self.id = self.name

    def get_competency(self, machine_type: str) -> float:
        """Return the competency multiplier for a given machine type.
        Lower is faster/better. Returns 1.0 (baseline) if not specified."""
        return self.competencyMultipliers.get(machine_type, 1.0)

@dataclass
class Circuit:
    id: str = ""
    name: str = ""
    zoneId: str = ""                   # The Area this circuit operates in
    diggerId: str = ""                 # The primary excavator
    truckIds: List[str] = field(default_factory=list) # The haul trucks servicing this digger
    dozerId: Optional[str] = None      # The destination dozer
    optimalTruckCount: int = 4         # The ideal number of trucks for this specific cycle length

    def __post_init__(self):
        if not self.id:
            self.id = self.name

@dataclass
class Machine:
    name: str
    type: str
    id: str = ""
    zoneId: str = ""
    transitTimeMinutes: int = 0
    currentOperatorId: Optional[str] = None
    status: str = 'operational'  # operational, not_required, maintenance, blast_exclusion, setup
    priority: int = 3  # For diggers (e.g., 1 is highest priority)

    def __post_init__(self):
        if not self.id:
            self.id = self.name

@dataclass
class Zone:
    name: str
    id: str = ""
    hasActiveBlast: bool = False
    x: float = 0.0
    y: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = self.name

@dataclass
class Assignment:
    id: str
    operatorId: str
    machineId: str
    startTime: str
    endTime: str = ""

@dataclass
class Break:
    id: str
    operatorId: str
    startTime: str
    endTime: str = ""

class BreakType(str, Enum):
    """Type of break for advanced BAP scheduling."""
    STANDARD = "standard"              # normal fixed-duration break
    FRACTIONABLE = "fractionable"      # can be split into sub-breaks
    VARIABLE = "variable"              # duration determined by fatigue level
    CIRCADIAN = "circadian"            # forced during circadian low-point window

@dataclass
class PlannedSegment:
    startTime: str
    endTime: str
    operatorName: str
    machineName: str = ""
    segmentType: str = "assignment"  # assignment, break, standby
    # ── Phase 2: Break metadata ──
    breakType: str = "standard"        # standard, fractionable, variable, circadian
    breakPartIndex: int = 0            # which part of a fractionable break (0-based)
    breakPartTotal: int = 1            # total parts of a fractionable break

@dataclass
class Settings:
    durationTimingBuffer: int = 15
    paddingMinutes: int = 5
    defaultOperatingTimeMinutes: int = 120
    breakDurationMinutes: int = 30  # All breaks end after 30 mins
    breakCooldownMinutes: int = 90  # Min minutes between breaks for same operator (1.5h - 2h)
    shiftBreakWindowStartOffsetMinutes: int = 120  # No breaks in first 2 hours (120 mins)
    shiftBreakWindowEndOffsetMinutes: int = 60  # No breaks ending in last 1 hour (60 mins)
    targetBreaksPerShift: int = 2  # Target breaks per 12h shift
    preferEvenWorkTime: bool = True
    autoPlanEnabled: bool = True
    # ── Phase 1: Handover & Fatigue Settings (§3.3, §4.2) ──
    handoverDurationMinutes: int = 5              # time for operator safety info exchange
    maxConsecutiveShifts: int = 4                  # hard block after N consecutive nights
    mandatoryResetHours: int = 48                  # required rest after consecutive limit
    circadianBreakWindowStart: str = "02:00"       # forced break window for night shifts
    circadianBreakWindowEnd: str = "04:00"         # end of circadian low-point window
    # ── Phase 1: Fatigue Model Parameters ──
    fatigueAccumulationRate: float = 1.0           # fatigue minutes per work minute
    fatigueRecoveryRate: float = 2.0               # fatigue recovery minutes per break minute
    alertnessWarningThreshold: float = 0.4         # alertness below this triggers warning
    alertnessCriticalThreshold: float = 0.2        # alertness below this triggers hard stop
    # ── Phase 2: Break Assignment Problem (BAP) Settings ──
    enableFractionableBreaks: bool = False         # allow splitting breaks into sub-breaks
    fractionableBreakParts: int = 2                # number of sub-breaks when fractionated
    minFractionDurationMinutes: int = 10           # minimum duration per sub-break
    enableVariableBreakLength: bool = False         # fatigue-based break duration
    variableBreakMinMinutes: int = 15              # minimum variable break
    variableBreakMaxMinutes: int = 45              # maximum variable break
    maxWorkstretchMinutes: int = 240               # hard limit: no more than 4h without break
    enableCircadianScheduling: bool = False         # force breaks during night-shift low-point
    # ── Phase 3: Solver Settings ──
    useAdvancedSolver: bool = True                  # try OR-Tools first, fallback to heuristic
    # ── Phase 4: Reactive Engine Settings ──
    lockedHorizonMinutes: int = 15                  # how much of the immediate future is locked from replanning

@dataclass
class ZoneConnection:
    zone_a: str
    zone_b: str
    travelTimeMinutes: int


# ──────────────────────────────────────────────────────────────
# Production Task (§6 — for future Phase 5 integration)
# ──────────────────────────────────────────────────────────────

@dataclass
class ProductionTask:
    """A unit of work to be scheduled on a machine.
    Enables production queue management and sequence optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    machineType: str = ""                          # required machine type
    requiredQualifications: List[str] = field(default_factory=list)
    estimatedDurationMinutes: float = 60
    priority: int = 5                              # 1 = highest, 10 = lowest
    predecessorTaskId: Optional[str] = None        # for sequencing
    setupTimeFromPrevious: Dict[str, float] = field(default_factory=dict)  # taskId -> minutes
    status: str = "pending"                        # pending, active, completed


# ──────────────────────────────────────────────────────────────
# Aggregate Application State
# ──────────────────────────────────────────────────────────────

CURRENT_SCHEMA_VERSION = 3  # Bump when adding new fields

@dataclass
class AppState:
    schemaVersion: int = CURRENT_SCHEMA_VERSION
    operators: List[Operator] = field(default_factory=list)
    machines: List[Machine] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    zoneConnections: List[ZoneConnection] = field(default_factory=list)
    circuits: List[Circuit] = field(default_factory=list)
    assignments: List[Assignment] = field(default_factory=list)
    breaks: List[Break] = field(default_factory=list)
    plannedSegments: List[PlannedSegment] = field(default_factory=list)
    productionTasks: List[ProductionTask] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    simulatedTime: str = ""

