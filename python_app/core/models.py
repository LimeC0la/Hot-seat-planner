from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Operator:
    name: str
    qualifications: List[str]
    id: str = ""
    status: str = 'standby'  # working, standby, on_break, absent
    standbyTimeMinutes: int = 0
    breaksTaken: int = 0
    currentAssignmentId: Optional[str] = None

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
    status: str = 'operational'  # operational, not_required, maintenance, blast_exclusion

    def __post_init__(self):
        if not self.id:
            self.id = self.name

@dataclass
class Zone:
    name: str
    id: str = ""
    hasActiveBlast: bool = False

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

@dataclass
class PlannedSegment:
    startTime: str
    endTime: str
    operatorName: str
    machineName: str = ""
    segmentType: str = "assignment"  # assignment, break, standby

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

@dataclass
class AppState:
    operators: List[Operator] = field(default_factory=list)
    machines: List[Machine] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    assignments: List[Assignment] = field(default_factory=list)
    breaks: List[Break] = field(default_factory=list)
    plannedSegments: List[PlannedSegment] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    simulatedTime: str = ""
