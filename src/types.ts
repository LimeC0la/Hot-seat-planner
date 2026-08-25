export type EquipmentType = 'Digger' | 'Truck' | 'Auxiliary' | 'ROM Loader';
export type Qualification = EquipmentType;

export interface Operator {
  id: string;
  name: string;
  qualifications: Qualification[];
  status: 'working' | 'standby' | 'on_break';
  standbyTimeMinutes: number; // Represents the ATB gauge (Active Time Battle)
  breaksTaken: number; // Max 3
  currentAssignmentId: string | null;
}

export interface Machine {
  id: string;
  name: string;
  type: EquipmentType;
  zoneId: string;
  currentOperatorId: string | null;
  status: 'operational' | 'blast_exclusion' | 'maintenance';
  transitTimeMinutes: number; // Travel time to break facilities
}

export interface Zone {
  id: string;
  name: string;
  hasActiveBlast: boolean;
}

// New interfaces for scheduling
export interface Assignment {
  id: string;
  operatorId: string;
  machineId: string;
  startTime: string; // ISO timestamp
  endTime: string;   // ISO timestamp
}

export interface Break {
  id: string;
  operatorId: string;
  startTime: string; // ISO timestamp
  endTime: string;   // ISO timestamp
}

export interface AppState {
  operators: Operator[];
  machines: Machine[];
  zones: Zone[];
  assignments: Assignment[];
  breaks: Break[];
  simulatedTime: string; // ISO string to simulate dashboard time
}

export type ViewMode = 'zone' | 'equipment' | 'operators';
