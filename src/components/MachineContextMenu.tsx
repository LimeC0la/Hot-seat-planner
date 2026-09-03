import React, { useEffect, useRef } from 'react';
import { useShiftStore } from '../core/store';
import { Machine, Circuit, MachineStatus } from '../core/types';
import { formatShortName } from '../core/planner';

interface MachineContextMenuProps {
  machine: Machine | null;
  circuit?: Circuit | null;
  position: { x: number; y: number } | null;
  onClose: () => void;
  onOpenDetail: (machine: Machine) => void;
  onOpenPreassign: (machine: Machine) => void;
}

export const MachineContextMenu: React.FC<MachineContextMenuProps> = ({
  machine,
  circuit,
  position,
  onClose,
  onOpenDetail,
  onOpenPreassign
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const {
    appState,
    setMachineStatus,
    setDozerRole,
    adjustCircuitCapacity,
    sendOnBreak,
    removeHotseatLock
  } = useShiftStore();

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent | TouchEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('touchstart', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('touchstart', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  if (!machine || !position) return null;

  const currentOp = machine.currentOperatorId;
  const isDozer = machine.type.toLowerCase().includes('dozer');
  const isDigger =
    machine.type.toLowerCase().includes('digger') ||
    machine.type.toLowerCase().includes('excavator') ||
    Boolean(circuit && (circuit.diggerId === machine.name || circuit.id === machine.name));

  const existingLock = (appState.manualReliefs || []).find(
    l => l.machineName === machine.name && l.locked
  );

  // Keep menu within viewport bounds
  const menuWidth = 260;
  const menuHeight = 340;
  const x = Math.min(position.x, window.innerWidth - menuWidth - 10);
  const y = Math.min(position.y, window.innerHeight - menuHeight - 10);

  return (
    <div
      ref={menuRef}
      className="fixed z-50 w-64 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl p-2.5 space-y-2 text-xs text-slate-200 select-none animate-in fade-in zoom-in-95 duration-100 backdrop-blur-md"
      style={{ left: `${Math.max(10, x)}px`, top: `${Math.max(10, y)}px` }}
      onClick={e => e.stopPropagation()}
    >
      {/* Header info */}
      <div className="pb-2 border-b border-slate-800 flex items-center justify-between">
        <div>
          <div className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
            <span>{isDigger ? '⛏️' : isDozer ? '🚜' : '🚛'}</span>
            <span>{machine.name}</span>
            <span className="text-[10px] text-slate-400 font-normal">({machine.type})</span>
          </div>
          <div className="text-[11px] text-slate-400 truncate">
            {currentOp ? (
              <span className="text-sky-300 font-medium">👷 {currentOp}</span>
            ) : (
              <span className="text-slate-500 italic">Uncrewed / Standby</span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1 text-xs rounded hover:bg-slate-800"
        >
          ✕
        </button>
      </div>

      {/* Status switch */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
          Machine State
        </div>
        <div className="grid grid-cols-2 gap-1">
          <button
            onClick={() => {
              setMachineStatus(machine.name, 'operational');
              onClose();
            }}
            className={`px-2 py-1.5 rounded text-center font-medium transition-colors ${
              machine.status === 'operational'
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 font-bold'
                : 'bg-slate-800/80 hover:bg-slate-750 text-slate-300'
            }`}
          >
            🟢 Operational
          </button>
          <button
            onClick={() => {
              const nextStatus: MachineStatus =
                machine.status === 'not_required' ? 'operational' : 'not_required';
              setMachineStatus(machine.name, nextStatus);
              onClose();
            }}
            className={`px-2 py-1.5 rounded text-center font-medium transition-colors ${
              machine.status === 'not_required'
                ? 'bg-amber-950/80 text-amber-300 border border-amber-700/60 font-bold'
                : 'bg-slate-800/80 hover:bg-slate-750 text-slate-300'
            }`}
          >
            🛑 Parked
          </button>
        </div>
      </div>

      {/* Dozer Specialization */}
      {isDozer && (
        <div className="space-y-1 pt-1 border-t border-slate-800">
          <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
            Dozer Operational Role
          </div>
          <div className="grid grid-cols-2 gap-1">
            <button
              onClick={() => {
                setDozerRole(machine.name, 'pit');
                onClose();
              }}
              className={`px-2 py-1 rounded text-[11px] text-center font-medium transition-colors ${
                (machine.dozerRole || 'pit') === 'pit'
                  ? 'bg-sky-950 text-sky-300 border border-sky-600 font-bold'
                  : 'bg-slate-800/70 hover:bg-slate-750 text-slate-400'
              }`}
              title="Parks simultaneously with digger to share Light Vehicle (LV) to crib"
            >
              🚜 Pit (LV Link)
            </button>
            <button
              onClick={() => {
                setDozerRole(machine.name, 'dump');
                onClose();
              }}
              className={`px-2 py-1 rounded text-[11px] text-center font-medium transition-colors ${
                machine.dozerRole === 'dump'
                  ? 'bg-amber-950 text-amber-300 border border-amber-600 font-bold'
                  : 'bg-slate-800/70 hover:bg-slate-750 text-slate-400'
              }`}
              title="Continuous tip head maintenance; remains active while haulage runs"
            >
              ⛰️ Dump (Continuous)
            </button>
          </div>
        </div>
      )}

      {/* Circuit Capacity (for diggers/circuits) */}
      {isDigger && circuit && (
        <div className="space-y-1 pt-1 border-t border-slate-800">
          <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 flex justify-between">
            <span>Optimal Truck Fleet</span>
            <span className="font-bold text-sky-400">{circuit.optimalTruckCount || 4} units</span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => adjustCircuitCapacity(circuit.id, -1)}
              className="flex-1 py-1 rounded bg-slate-800 hover:bg-slate-750 text-slate-200 font-bold"
              title="Decrease optimal truck count"
            >
              - 1 Truck
            </button>
            <button
              onClick={() => adjustCircuitCapacity(circuit.id, 1)}
              className="flex-1 py-1 rounded bg-slate-800 hover:bg-slate-750 text-slate-200 font-bold"
              title="Increase optimal truck count"
            >
              + 1 Truck
            </button>
          </div>
        </div>
      )}

      {/* Preassign Hotseat Relief */}
      <div className="space-y-1 pt-1 border-t border-slate-800">
        <div className="text-[10px] uppercase tracking-wider font-semibold text-slate-400">
          Hotseat Relief Assignment
        </div>
        {existingLock ? (
          <div className="p-1.5 bg-emerald-950/40 border border-emerald-800/60 rounded flex items-center justify-between text-[11px]">
            <div className="truncate pr-1">
              <span className="text-emerald-300 font-bold">🔒 {formatShortName(existingLock.reliefOperatorName)}</span>
              <span className="text-[10px] text-slate-400 block">Preassigned</span>
            </div>
            <button
              onClick={() => removeHotseatLock(existingLock.id)}
              className="px-2 py-0.5 text-[10px] bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded"
              title="Remove preassigned relief lock"
            >
              Unlock
            </button>
          </div>
        ) : (
          <button
            onClick={() => {
              onOpenPreassign(machine);
              onClose();
            }}
            className="w-full py-1 px-2 text-left rounded bg-slate-800/80 hover:bg-sky-950/60 hover:text-sky-300 border border-slate-700/60 flex items-center gap-1.5 text-[11px]"
          >
            <span>🔒</span>
            <span>Preassign Specific Operator...</span>
          </button>
        )}
      </div>

      {/* Immediate operational actions */}
      <div className="pt-1 border-t border-slate-800 space-y-1">
        {currentOp && (
          <button
            onClick={() => {
              sendOnBreak(currentOp);
              onClose();
            }}
            className="w-full py-1 px-2 text-left rounded bg-purple-950/40 hover:bg-purple-900/60 text-purple-300 flex items-center gap-1.5"
          >
            <span>☕</span>
            <span>Send Driver on Break Now</span>
          </button>
        )}

        <button
          onClick={() => {
            onOpenDetail(machine);
            onClose();
          }}
          className="w-full py-1 px-2 text-left rounded bg-slate-800/80 hover:bg-slate-750 text-slate-300 flex items-center gap-1.5"
        >
          <span>🔍</span>
          <span>Open Full Machine Inspector...</span>
        </button>
      </div>
    </div>
  );
};
