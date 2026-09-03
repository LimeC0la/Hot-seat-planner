import React from 'react';
import { useShiftStore } from '../core/store';
import { Machine, Circuit } from '../core/types';
import { getMachineOperationalShell } from '../core/planner';

interface MachineDetailModalProps {
  machine: Machine | null;
  circuit?: Circuit | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenPreassign: (machine: Machine) => void;
}

export const MachineDetailModal: React.FC<MachineDetailModalProps> = ({
  machine,
  circuit,
  isOpen,
  onClose,
  onOpenPreassign
}) => {
  const {
    appState,
    setMachineStatus,
    setDozerRole,
    adjustCircuitCapacity,
    sendOnBreak,
    returnPrimaryOperator,
    removeHotseatLock
  } = useShiftStore();

  if (!isOpen || !machine) return null;

  const shell = getMachineOperationalShell(machine, appState.circuits);
  const currentOp = appState.operators.find(o => o.name === machine.currentOperatorId);
  const isDozer = machine.type.toLowerCase().includes('dozer');
  const isDigger =
    machine.type.toLowerCase().includes('digger') ||
    machine.type.toLowerCase().includes('excavator') ||
    Boolean(circuit && (circuit.diggerId === machine.name || circuit.id === machine.name));

  const existingLock = (appState.manualReliefs || []).find(
    l => l.machineName === machine.name && l.locked
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-750 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">
              {isDigger ? '⛏️' : isDozer ? '🚜' : machine.type.includes('Truck') ? '🚛' : '🛠️'}
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <span>{machine.name}</span>
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-slate-800 text-slate-300 rounded border border-slate-700">
                  {machine.type}
                </span>
                <span
                  className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                    machine.status === 'operational'
                      ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60'
                      : 'bg-amber-950/80 text-amber-300 border border-amber-700/60'
                  }`}
                >
                  {machine.status === 'operational' ? 'Operational' : 'Parked'}
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Location: {machine.zoneId || 'Unassigned'} • Priority {machine.priority}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
          {/* Operational Shell Classification */}
          <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 space-y-1.5">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
              Operational Shell & Coupling
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-slate-200 text-sm">
                  {shell === 'circuit_leader'
                    ? 'Inner Core: Primary Loading Tool (Digger)'
                    : shell === 'circuit_truck'
                    ? 'Inner Core: Dedicated Haul Fleet'
                    : shell === 'bench_support'
                    ? 'Middle Shell: Bench & Dump Support'
                    : 'Outer Shell: Ancillary Pit Services'}
                </div>
                <div className="text-[11px] text-slate-400">
                  {shell === 'circuit_leader' || shell === 'circuit_truck'
                    ? '100% Coupled: Digger & trucks evaluate for simultaneous crib if no relief available.'
                    : shell === 'bench_support'
                    ? 'Semi-Independent: Absorbs operational buffers; aligns with digger or dump haulage.'
                    : 'Decoupled: Fully independent continuous service (road grading & dust suppression).'}
                </div>
              </div>
            </div>
          </div>

          {/* Assigned Driver Status */}
          <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 space-y-2">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 flex items-center justify-between">
              <span>Assigned Primary Operator</span>
              {currentOp && (
                <span className="text-sky-400 font-normal">
                  Breaks taken today: {currentOp.breaksTaken || 0}
                </span>
              )}
            </div>

            {/* Active Relief In Progress Banner */}
            {machine.reliefOperatorId && machine.primaryOperatorId ? (
              <div className="p-3 bg-emerald-950/40 rounded-xl border border-emerald-700/60 flex items-center justify-between">
                <div>
                  <div className="font-bold text-emerald-300 text-xs flex items-center gap-1.5">
                    <span>⚡</span> Active Hotseat Relief in Progress
                  </div>
                  <div className="text-[11px] text-slate-300 mt-0.5">
                    <span className="font-semibold text-emerald-400">{machine.reliefOperatorId}</span> is covering for{' '}
                    <span className="font-semibold text-sky-400">{machine.primaryOperatorId}</span> (on crib)
                  </div>
                </div>
                <button
                  onClick={() => returnPrimaryOperator(machine.name)}
                  className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white font-bold rounded-lg shadow cursor-pointer text-xs"
                >
                  Return Primary Driver
                </button>
              </div>
            ) : currentOp ? (
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-slate-100 flex items-center gap-1.5">
                    <span>👷</span>
                    <span>{currentOp.name}</span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Qualifications: {currentOp.qualifications.join(', ')}
                  </div>
                </div>
                <button
                  onClick={() => sendOnBreak(currentOp.name)}
                  className="px-3 py-1.5 bg-purple-950/80 hover:bg-purple-900 border border-purple-700/60 text-purple-300 font-bold rounded-lg transition-colors cursor-pointer flex items-center gap-1"
                >
                  <span>☕</span> Send to Break
                </button>
              </div>
            ) : (
              <div className="py-2 text-center text-slate-500 italic">
                No operator currently assigned to this machine.
              </div>
            )}
          </div>

          {/* Circuit Capacity (for diggers) */}
          {isDigger && circuit && (
            <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 space-y-2">
              <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 flex items-center justify-between">
                <span>Haul Circuit: {circuit.name}</span>
                <span className="font-bold text-sky-400">
                  Target: {circuit.optimalTruckCount || 4} Trucks
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => adjustCircuitCapacity(circuit.id, -1)}
                  className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-750 font-bold text-slate-200 rounded-lg"
                >
                  - Decrease Capacity
                </button>
                <button
                  onClick={() => adjustCircuitCapacity(circuit.id, 1)}
                  className="flex-1 py-1.5 bg-slate-800 hover:bg-slate-750 font-bold text-slate-200 rounded-lg"
                >
                  + Increase Capacity
                </button>
              </div>
            </div>
          )}

          {/* Dozer Specialization (for dozers) */}
          {isDozer && (
            <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 space-y-2">
              <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                Dozer Operational Role
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setDozerRole(machine.name, 'pit')}
                  className={`p-2.5 rounded-xl text-left border transition-all ${
                    (machine.dozerRole || 'pit') === 'pit'
                      ? 'bg-sky-950/80 border-sky-600 text-sky-200 shadow'
                      : 'bg-slate-800/60 border-slate-750 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <div className="font-bold text-sm">🚜 Pit Dozer</div>
                  <div className="text-[10px] opacity-80 mt-0.5">
                    Preps bench floors. Aligns with digger crib to share Light Vehicle (LV) transit.
                  </div>
                </button>
                <button
                  onClick={() => setDozerRole(machine.name, 'dump')}
                  className={`p-2.5 rounded-xl text-left border transition-all ${
                    machine.dozerRole === 'dump'
                      ? 'bg-amber-950/80 border-amber-600 text-amber-200 shadow'
                      : 'bg-slate-800/60 border-slate-750 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <div className="font-bold text-sm">⛰️ Dump Dozer</div>
                  <div className="text-[10px] opacity-80 mt-0.5">
                    Tip head crest safety. Stays active while any circuit is hauling dirt.
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Preassigned Hotseat Lock */}
          <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 space-y-2">
            <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 flex items-center justify-between">
              <span>Manual Hotseat Pre-assignment</span>
              {existingLock && (
                <span className="px-2 py-0.5 text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800 rounded font-bold">
                  🔒 Locked
                </span>
              )}
            </div>

            {existingLock ? (
              <div className="p-2.5 bg-emerald-950/30 border border-emerald-800/50 rounded-lg flex items-center justify-between">
                <div>
                  <div className="font-bold text-emerald-300">
                    {existingLock.reliefOperatorName}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Window:{' '}
                    {new Date(existingLock.startTime).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}{' '}
                    -{' '}
                    {new Date(existingLock.endTime).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                </div>
                <button
                  onClick={() => removeHotseatLock(existingLock.id)}
                  className="px-2.5 py-1 text-xs bg-rose-900/80 hover:bg-rose-800 text-rose-200 font-bold rounded-lg"
                >
                  Remove Lock
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  onOpenPreassign(machine);
                  onClose();
                }}
                className="w-full py-2 bg-slate-800 hover:bg-sky-950 hover:text-sky-300 border border-slate-750 hover:border-sky-600/60 font-bold text-slate-300 rounded-lg flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>🔒</span>
                <span>Preassign Specific Operator & Time Window...</span>
              </button>
            )}
          </div>

          {/* Machine State Controls */}
          <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 flex items-center justify-between">
            <div>
              <div className="font-bold text-slate-200">Machine Status Toggle</div>
              <div className="text-[11px] text-slate-400">
                Current:{' '}
                <span className="font-semibold text-slate-300 capitalize">{machine.status}</span>
              </div>
            </div>
            <button
              onClick={() => {
                const next = machine.status === 'operational' ? 'not_required' : 'operational';
                setMachineStatus(machine.name, next);
              }}
              className={`px-3.5 py-1.5 font-bold rounded-lg shadow cursor-pointer ${
                machine.status === 'operational'
                  ? 'bg-amber-900/80 hover:bg-amber-800 text-amber-200 border border-amber-700'
                  : 'bg-emerald-700 hover:bg-emerald-600 text-white'
              }`}
            >
              {machine.status === 'operational' ? 'Park Machine' : 'Set Operational'}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-850 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
