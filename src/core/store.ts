import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AppState, Assignment, MachineStatus, Settings, ManualReliefLock } from './types';
import { INITIAL_STATE } from './initialState';
import { ReliefPlanner } from './planner';

interface ShiftStore {
  appState: AppState;
  currentTime: string; // ISO string for easy serialization
  isLiveTime: boolean; // if true, ticks with system clock

  // Time & Simulation
  tick: () => void;
  setCurrentTime: (iso: string) => void;
  setLiveTime: (live: boolean) => void;
  resetShiftTo0700: () => void;

  // Actions
  recomputePlan: () => void;
  assignOperator: (operatorId: string, machineId: string) => void;
  unassignMachine: (machineId: string) => void;
  sendOnBreak: (operatorId: string) => void;
  returnFromBreak: (operatorId: string) => void;
  setOperatorAbsent: (operatorId: string, absent: boolean) => void;
  setMachineStatus: (machineId: string, status: MachineStatus) => void;
  relieveOperatorOnMachine: (machineName: string, reliefOpName: string) => void;
  returnPrimaryOperator: (machineName: string) => void;

  // Machine & Circuit Adjustments
  adjustCircuitCapacity: (circuitId: string, delta: number) => void;
  setDozerRole: (machineName: string, role: 'pit' | 'dump') => void;
  setAreaShutdownMode: (zoneId: string, mode: 'simultaneous' | 'staggered', staggerMinutes?: number) => void;
  setCircuitShutdownMode: (circuitId: string, mode: 'simultaneous' | 'staggered', offsetMinutes?: number) => void;

  // Manual Relief Locks
  preassignHotseat: (lock: {
    machineName: string;
    reliefOperatorName: string;
    startTime: string;
    endTime: string;
  }) => void;
  removeHotseatLock: (lockId: string) => void;

  // Setup Wizard
  applyDailyAllocation: (params: {
    allocations: Record<string, string | null>;
    absentOperators: string[];
    notRequiredMachines: string[];
    resetShiftTime: boolean;
  }) => void;

  // Settings & Storage
  updateSettings: (newSettings: Partial<Settings>) => void;
  exportStateJson: () => string;
  importStateJson: (jsonStr: string) => boolean;
  resetToDefaultState: () => void;
}

export const useShiftStore = create<ShiftStore>()(
  persist(
    (set, get) => ({
      appState: INITIAL_STATE,
      currentTime: new Date().toISOString(),
      isLiveTime: true,

      tick: () => {
        const { isLiveTime, recomputePlan } = get();
        if (isLiveTime) {
          const nowIso = new Date().toISOString();
          set({ currentTime: nowIso });
          recomputePlan();
        }
      },

      setCurrentTime: (iso: string) => {
        set({ currentTime: iso, isLiveTime: false });
        get().recomputePlan();
      },

      setLiveTime: (live: boolean) => {
        set({ isLiveTime: live, currentTime: new Date().toISOString() });
        get().recomputePlan();
      },

      resetShiftTo0700: () => {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 7, 0, 0, 0);
        set({ currentTime: start.toISOString(), isLiveTime: false });
        get().recomputePlan();
      },

      recomputePlan: () => {
        const { appState, currentTime } = get();
        try {
          const planner = new ReliefPlanner(appState);
          const segments = planner.generatePlan(new Date(currentTime));
          set({
            appState: {
              ...appState,
              plannedSegments: segments
            }
          });
        } catch (e) {
          console.error('Plan calculation error:', e);
        }
      },

      assignOperator: (operatorId: string, machineId: string) => {
        const { appState, currentTime } = get();
        const operators = appState.operators.map(op => {
          if (op.name === operatorId || op.id === operatorId) {
            return {
              ...op,
              status: 'working' as const,
              currentAssignmentId: machineId
            };
          }
          // If this operator was previously on the machine, unassign them
          if (op.currentAssignmentId === machineId) {
            return {
              ...op,
              status: 'standby' as const,
              currentAssignmentId: null
            };
          }
          return op;
        });

        const machines = appState.machines.map(m => {
          if (m.name === machineId || m.id === machineId) {
            return {
              ...m,
              currentOperatorId: operatorId,
              status: 'operational' as const
            };
          }
          return m;
        });

        // Add new assignment record
        const newAssignment = {
          id: `assign_${Date.now()}`,
          operatorId,
          machineId,
          startTime: currentTime,
          endTime: ''
        };

        set({
          appState: {
            ...appState,
            operators,
            machines,
            assignments: [...appState.assignments, newAssignment]
          }
        });

        get().recomputePlan();
      },

      unassignMachine: (machineId: string) => {
        const { appState, currentTime } = get();
        let vacatedOperator: string | null = null;

        const machines = appState.machines.map(m => {
          if (m.name === machineId || m.id === machineId) {
            vacatedOperator = m.currentOperatorId;
            return { ...m, currentOperatorId: null };
          }
          return m;
        });

        const operators = appState.operators.map(op => {
          if (vacatedOperator && (op.name === vacatedOperator || op.id === vacatedOperator)) {
            return { ...op, status: 'standby' as const, currentAssignmentId: null };
          }
          return op;
        });

        // Close assignment
        const assignments = appState.assignments.map(a => {
          if (a.machineId === machineId && !a.endTime) {
            return { ...a, endTime: currentTime };
          }
          return a;
        });

        set({
          appState: {
            ...appState,
            machines,
            operators,
            assignments
          }
        });

        get().recomputePlan();
      },

      sendOnBreak: (operatorId: string) => {
        const { appState, currentTime } = get();
        let targetMachineId: string | null = null;

        const operators = appState.operators.map(op => {
          if (op.name === operatorId || op.id === operatorId) {
            targetMachineId = op.currentAssignmentId;
            return {
              ...op,
              status: 'on_break' as const,
              currentAssignmentId: null,
              breaksTaken: (op.breaksTaken || 0) + 1
            };
          }
          return op;
        });

        const machines = appState.machines.map(m => {
          if (targetMachineId && (m.name === targetMachineId || m.id === targetMachineId)) {
            return { ...m, currentOperatorId: null };
          }
          return m;
        });

        // Close assignment if running
        const assignments = appState.assignments.map(a => {
          if (a.operatorId === operatorId && !a.endTime) {
            return { ...a, endTime: currentTime };
          }
          return a;
        });

        // Record break start
        const newBreak = {
          id: `break_${Date.now()}`,
          operatorId,
          startTime: currentTime,
          endTime: ''
        };

        set({
          appState: {
            ...appState,
            operators,
            machines,
            assignments,
            breaks: [...appState.breaks, newBreak]
          }
        });

        get().recomputePlan();
      },

      returnFromBreak: (operatorId: string) => {
        const { appState, currentTime, returnPrimaryOperator } = get();

        // Check if operatorId is the primaryOperatorId of any machine currently under relief
        const machineUnderRelief = appState.machines.find(
          m => (m.primaryOperatorId === operatorId) && m.reliefOperatorId
        );
        if (machineUnderRelief) {
          returnPrimaryOperator(machineUnderRelief.name);
          return;
        }

        const operators = appState.operators.map(op => {
          if (op.name === operatorId || op.id === operatorId) {
            return {
              ...op,
              status: 'standby' as const
            };
          }
          return op;
        });

        const breaks = appState.breaks.map(b => {
          if (b.operatorId === operatorId && !b.endTime) {
            return { ...b, endTime: currentTime };
          }
          return b;
        });

        set({
          appState: {
            ...appState,
            operators,
            breaks
          }
        });

        get().recomputePlan();
      },

      setOperatorAbsent: (operatorId: string, absent: boolean) => {
        const { appState } = get();
        const operators = appState.operators.map(op => {
          if (op.name === operatorId || op.id === operatorId) {
            return {
              ...op,
              status: absent ? ('absent' as const) : ('standby' as const),
              currentAssignmentId: absent ? null : op.currentAssignmentId
            };
          }
          return op;
        });

        set({
          appState: {
            ...appState,
            operators
          }
        });

        get().recomputePlan();
      },

      setMachineStatus: (machineId: string, status: MachineStatus) => {
        const { appState } = get();
        const machines = appState.machines.map(m => {
          if (m.name === machineId || m.id === machineId) {
            return {
              ...m,
              status,
              currentOperatorId: status === 'operational' ? m.currentOperatorId : null
            };
          }
          return m;
        });

        set({
          appState: {
            ...appState,
            machines
          }
        });

        get().recomputePlan();
      },

      relieveOperatorOnMachine: (machineName: string, reliefOpName: string) => {
        const { appState, currentTime } = get();
        const machine = appState.machines.find(m => m.name === machineName || m.id === machineName);
        if (!machine) return;

        const outgoingOpName = machine.currentOperatorId;

        // 1. Put outgoing operator on break
        let operators = appState.operators.map(op => {
          if (outgoingOpName && (op.name === outgoingOpName || op.id === outgoingOpName)) {
            return {
              ...op,
              status: 'on_break' as const,
              currentAssignmentId: null,
              breaksTaken: (op.breaksTaken || 0) + 1
            };
          }
          if (op.name === reliefOpName || op.id === reliefOpName) {
            return {
              ...op,
              status: 'working' as const,
              currentAssignmentId: machineName
            };
          }
          return op;
        });

        // 2. Assign relief operator to machine
        const machines = appState.machines.map(m => {
          if (m.name === machineName || m.id === machineName) {
            const primaryOp = m.primaryOperatorId || outgoingOpName;
            return {
              ...m,
              primaryOperatorId: primaryOp,
              reliefOperatorId: reliefOpName,
              currentOperatorId: reliefOpName,
              status: 'operational' as const
            };
          }
          return m;
        });

        // 3. Close outgoing assignment, start relief assignment, start outgoing break
        const assignments = appState.assignments.map(a => {
          if (outgoingOpName && a.operatorId === outgoingOpName && !a.endTime) {
            return { ...a, endTime: currentTime };
          }
          return a;
        });

        assignments.push({
          id: `assign_${Date.now()}`,
          operatorId: reliefOpName,
          machineId: machineName,
          startTime: currentTime,
          endTime: ''
        });

        const breaks = [...appState.breaks];
        if (outgoingOpName) {
          breaks.push({
            id: `break_${Date.now()}`,
            operatorId: outgoingOpName,
            startTime: currentTime,
            endTime: ''
          });
        }

        set({
          appState: {
            ...appState,
            operators,
            machines,
            assignments,
            breaks
          }
        });

        get().recomputePlan();
      },

      returnPrimaryOperator: (machineName: string) => {
        const { appState, currentTime } = get();
        const machine = appState.machines.find(m => m.name === machineName || m.id === machineName);
        if (!machine) return;

        const primaryOpName = machine.primaryOperatorId;
        const currentReliefOpName = machine.reliefOperatorId;
        if (!primaryOpName) return;

        // 1. Return primary operator to working on machine, return relief operator to standby
        const operators = appState.operators.map(op => {
          if (op.name === primaryOpName || op.id === primaryOpName) {
            return {
              ...op,
              status: 'working' as const,
              currentAssignmentId: machineName
            };
          }
          if (currentReliefOpName && (op.name === currentReliefOpName || op.id === currentReliefOpName)) {
            return {
              ...op,
              status: 'standby' as const,
              currentAssignmentId: null
            };
          }
          return op;
        });

        // 2. Update machine
        const machines = appState.machines.map(m => {
          if (m.name === machineName || m.id === machineName) {
            return {
              ...m,
              currentOperatorId: primaryOpName,
              reliefOperatorId: null
            };
          }
          return m;
        });

        // 3. Close relief assignment, close primary break, start primary assignment
        const assignments = appState.assignments.map(a => {
          if (
            currentReliefOpName &&
            a.operatorId === currentReliefOpName &&
            a.machineId === machineName &&
            !a.endTime
          ) {
            return { ...a, endTime: currentTime };
          }
          return a;
        });

        assignments.push({
          id: `assign_${Date.now()}`,
          operatorId: primaryOpName,
          machineId: machineName,
          startTime: currentTime,
          endTime: ''
        });

        const breaks = appState.breaks.map(b => {
          if (b.operatorId === primaryOpName && !b.endTime) {
            return { ...b, endTime: currentTime };
          }
          return b;
        });

        set({
          appState: {
            ...appState,
            operators,
            machines,
            assignments,
            breaks
          }
        });

        get().recomputePlan();
      },

      adjustCircuitCapacity: (circuitId: string, delta: number) => {
        const { appState } = get();
        const circuits = appState.circuits.map(c => {
          if (c.id === circuitId || c.name === circuitId || c.diggerId === circuitId) {
            const nextCount = Math.max(0, (c.optimalTruckCount || 0) + delta);
            return { ...c, optimalTruckCount: nextCount };
          }
          return c;
        });
        set({ appState: { ...appState, circuits } });
        get().recomputePlan();
      },

      setDozerRole: (machineName: string, role: 'pit' | 'dump') => {
        const { appState } = get();
        const machines = appState.machines.map(m => {
          if (m.name === machineName || m.id === machineName) {
            return { ...m, dozerRole: role };
          }
          return m;
        });
        set({ appState: { ...appState, machines } });
        get().recomputePlan();
      },

      setAreaShutdownMode: (zoneId: string, mode: 'simultaneous' | 'staggered', staggerMinutes: number = 30) => {
        const { appState } = get();
        const areaShutdownConfigs = {
          ...(appState.areaShutdownConfigs || {}),
          [zoneId]: { zoneId, mode, staggerMinutes }
        };
        set({ appState: { ...appState, areaShutdownConfigs } });
        get().recomputePlan();
      },

      setCircuitShutdownMode: (circuitId: string, mode: 'simultaneous' | 'staggered', offsetMinutes?: number) => {
        const { appState } = get();
        const circuits = appState.circuits.map(c => {
          if (c.id === circuitId || c.name === circuitId || c.diggerId === circuitId) {
            return {
              ...c,
              shutdownMode: mode,
              staggerOffsetMinutes: offsetMinutes ?? c.staggerOffsetMinutes ?? 30
            };
          }
          return c;
        });
        set({ appState: { ...appState, circuits } });
        get().recomputePlan();
      },

      preassignHotseat: (lockData) => {
        const { appState } = get();
        const newLock: ManualReliefLock = {
          id: `lock_${Date.now()}_${lockData.machineName}`,
          ...lockData,
          locked: true
        };
        const manualReliefs = [
          ...(appState.manualReliefs || []).filter(l => l.machineName !== lockData.machineName),
          newLock
        ];
        set({ appState: { ...appState, manualReliefs } });
        get().recomputePlan();
      },

      removeHotseatLock: (lockId: string) => {
        const { appState } = get();
        const manualReliefs = (appState.manualReliefs || []).filter(l => l.id !== lockId);
        set({ appState: { ...appState, manualReliefs } });
        get().recomputePlan();
      },

      applyDailyAllocation: ({ allocations, absentOperators, notRequiredMachines, resetShiftTime }) => {
        const { appState } = get();
        const absentSet = new Set(absentOperators);
        const nrSet = new Set(notRequiredMachines);

        const now = new Date();
        const shiftStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 7, 0, 0, 0);
        const effectiveTime = resetShiftTime ? shiftStart.toISOString() : get().currentTime;

        const newAssignments: Assignment[] = [];

        const machines = appState.machines.map(m => {
          const isNR = nrSet.has(m.name);
          const assignedOp = isNR ? null : allocations[m.name] || null;

          if (assignedOp) {
            newAssignments.push({
              id: `assign_${Date.now()}_${m.name}`,
              operatorId: assignedOp,
              machineId: m.name,
              startTime: effectiveTime,
              endTime: ''
            });
          }

          return {
            ...m,
            status: isNR ? ('not_required' as const) : ('operational' as const),
            currentOperatorId: assignedOp,
            primaryOperatorId: assignedOp,
            reliefOperatorId: null
          };
        });

        // Build assigned set
        const assignedOpSet = new Set(Object.values(allocations).filter(Boolean) as string[]);

        const operators = appState.operators.map(op => {
          if (absentSet.has(op.name)) {
            return { ...op, status: 'absent' as const, currentAssignmentId: null };
          }
          if (assignedOpSet.has(op.name)) {
            // Find machine
            const machEntry = Object.entries(allocations).find(([, opName]) => opName === op.name);
            return {
              ...op,
              status: 'working' as const,
              currentAssignmentId: machEntry ? machEntry[0] : null
            };
          }
          return {
            ...op,
            status: 'standby' as const,
            currentAssignmentId: null
          };
        });

        set({
          currentTime: effectiveTime,
          appState: {
            ...appState,
            operators,
            machines,
            assignments: newAssignments,
            breaks: []
          }
        });

        get().recomputePlan();
      },

      updateSettings: (newSettings: Partial<Settings>) => {
        const { appState } = get();
        set({
          appState: {
            ...appState,
            settings: { ...appState.settings, ...newSettings }
          }
        });
        get().recomputePlan();
      },

      exportStateJson: () => {
        return JSON.stringify(get().appState, null, 2);
      },

      importStateJson: (jsonStr: string) => {
        try {
          const parsed = JSON.parse(jsonStr) as AppState;
          if (parsed && Array.isArray(parsed.operators) && Array.isArray(parsed.machines)) {
            set({ appState: parsed });
            get().recomputePlan();
            return true;
          }
        } catch (e) {
          console.error('Import failed:', e);
        }
        return false;
      },

      resetToDefaultState: () => {
        set({ appState: INITIAL_STATE });
        get().recomputePlan();
      }
    }),
    {
      name: 'hotseat_shift_storage',
      partialize: state => ({ appState: state.appState })
    }
  )
);
