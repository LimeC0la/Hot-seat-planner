export type OperatorStatus = 'working' | 'standby' | 'on_break' | 'absent' | 'fatigued';
export type MachineStatus = 'operational' | 'not_required' | 'maintenance' | 'blast_exclusion' | 'setup';

export interface Operator {
  id: string;
  name: string;
  qualifications: string[];
  status: OperatorStatus;
  standbyTimeMinutes: number;
  breaksTaken: number;
  currentAssignmentId: string | null;
  competencyMultipliers?: Record<string, number>;
  cumulativeFatigueMinutes?: number;
  consecutiveShiftsWorked?: number;
  lastFullRestEnd?: string | null;
  alertnessScore?: number;
}

export interface Machine {
  id: string;
  name: string;
  type: string;
  zoneId: string;
  transitTimeMinutes: number;
  currentOperatorId: string | null;
  status: MachineStatus;
  priority: number;
}

export interface Zone {
  id: string;
  name: string;
  hasActiveBlast?: boolean;
  x?: number;
  y?: number;
}

export interface ZoneConnection {
  zone_a: string;
  zone_b: string;
  travelTimeMinutes: number;
}

export interface Circuit {
  id: string;
  name: string;
  zoneId: string;
  diggerId: string;
  truckIds: string[];
  dozerId: string | null;
  optimalTruckCount: number;
}

export interface Assignment {
  id: string;
  operatorId: string;
  machineId: string;
  startTime: string;
  endTime: string;
}

export interface Break {
  id: string;
  operatorId: string;
  startTime: string;
  endTime: string;
}

export interface PlannedSegment {
  startTime: string;
  endTime: string;
  operatorName: string;
  machineName: string;
  segmentType: 'assignment' | 'break' | 'standby';
  breakType?: 'standard' | 'fractionable' | 'variable' | 'circadian';
}

export interface Settings {
  durationTimingBuffer: number;
  paddingMinutes: number;
  defaultOperatingTimeMinutes: number;
  breakDurationMinutes: number;
  breakCooldownMinutes: number;
  shiftBreakWindowStartOffsetMinutes: number;
  shiftBreakWindowEndOffsetMinutes: number;
  targetBreaksPerShift: number;
  preferEvenWorkTime: boolean;
  autoPlanEnabled: boolean;
  maxWorkstretchMinutes: number;
  handoverDurationMinutes: number;
  [key: string]: any;
}

export interface AppState {
  schemaVersion: number;
  operators: Operator[];
  machines: Machine[];
  zones: Zone[];
  zoneConnections: ZoneConnection[];
  circuits: Circuit[];
  assignments: Assignment[];
  breaks: Break[];
  plannedSegments: PlannedSegment[];
  settings: Settings;
  simulatedTime: string;
}
