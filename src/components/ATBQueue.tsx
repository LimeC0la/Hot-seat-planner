import React from 'react';
import { useShiftStore } from '../core/store';
import { formatShortName } from '../core/planner';

export const ATBQueue: React.FC = () => {
  const { appState, returnFromBreak, relieveOperatorOnMachine } = useShiftStore();

  const operators = appState.operators;
  const machines = appState.machines;
  const targetBreaks = appState.settings.targetBreaksPerShift;

  const onBreakOps = operators.filter(o => o.status === 'on_break');
  const standbyOps = operators.filter(o => o.status === 'standby');
  const workingOps = operators.filter(o => o.status === 'working');
  const operationalMachines = machines.filter(m => m.status === 'operational');

  // Operators needing breaks most (breaksTaken < targetBreaks)
  const needingBreakOps = workingOps
    .filter(o => (o.breaksTaken || 0) < targetBreaks)
    .sort((a, b) => (a.breaksTaken || 0) - (b.breaksTaken || 0));

  return (
    <div className="w-72 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col h-full overflow-hidden select-none">
      {/* Top Metrics Banner */}
      <div className="p-4 border-b border-slate-800 bg-slate-850/60">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Shift Live Pulse</h3>
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
            <div className="text-xl font-black text-sky-400">{operationalMachines.length}</div>
            <div className="text-[10px] uppercase font-semibold text-slate-500">Active Units</div>
          </div>
          <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
            <div className="text-xl font-black text-amber-400">{standbyOps.length}</div>
            <div className="text-[10px] uppercase font-semibold text-slate-500">Floaters</div>
          </div>
        </div>
      </div>

      {/* Scrollable sections */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Section 1: Floater / Standby Relief Pool */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
              <span>⏳</span> Available Relief Pool ({standbyOps.length})
            </span>
          </div>

          {standbyOps.length === 0 ? (
            <div className="p-2.5 text-center text-xs text-slate-500 bg-slate-950/40 rounded border border-dashed border-slate-800">
              No spare floaters available
            </div>
          ) : (
            <div className="space-y-1.5">
              {standbyOps.map(op => (
                <div
                  key={op.id}
                  className="p-2 bg-slate-850 rounded border border-amber-900/30 flex items-center justify-between"
                >
                  <div className="min-w-0 pr-1">
                    <div className="text-xs font-bold text-slate-200 truncate">{formatShortName(op.name)}</div>
                    <div className="text-[10px] text-slate-400 truncate">{op.qualifications.join(', ')}</div>
                  </div>
                  <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded">
                    Ready
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Section 2: Currently on Break */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-purple-300 flex items-center gap-1.5">
              <span>☕</span> Currently On Break ({onBreakOps.length})
            </span>
          </div>

          {onBreakOps.length === 0 ? (
            <div className="p-2.5 text-center text-xs text-slate-500 bg-slate-950/40 rounded border border-dashed border-slate-800">
              No operators on break
            </div>
          ) : (
            <div className="space-y-1.5">
              {onBreakOps.map(op => (
                <div
                  key={op.id}
                  className="p-2 bg-slate-850 rounded border border-purple-900/40 flex items-center justify-between"
                >
                  <div className="min-w-0 pr-1">
                    <div className="text-xs font-bold text-purple-200 truncate">{formatShortName(op.name)}</div>
                    <div className="text-[10px] text-slate-400">Crib {op.breaksTaken}/{targetBreaks}</div>
                  </div>
                  <button
                    onClick={() => returnFromBreak(op.name)}
                    className="px-2 py-1 text-[10px] font-bold bg-purple-700 hover:bg-purple-600 text-white rounded shadow cursor-pointer"
                  >
                    Return
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Section 3: Due for Relief */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-sky-300 flex items-center gap-1.5">
              <span>⏰</span> Next In Line for Crib ({needingBreakOps.length})
            </span>
          </div>

          <div className="space-y-1.5">
            {needingBreakOps.slice(0, 5).map(op => (
              <div
                key={op.id}
                className="p-2 bg-slate-850 rounded border border-slate-800 flex items-center justify-between text-xs"
              >
                <div className="min-w-0 pr-1">
                  <div className="font-semibold text-slate-300 truncate">{formatShortName(op.name)}</div>
                  <div className="text-[10px] text-sky-400">🚜 {op.currentAssignmentId || 'Machine'}</div>
                </div>
                {standbyOps.length > 0 && op.currentAssignmentId && (
                  <button
                    onClick={() => {
                      const relief = standbyOps[0];
                      if (relief && op.currentAssignmentId) {
                        relieveOperatorOnMachine(op.currentAssignmentId, relief.name);
                      }
                    }}
                    className="px-1.5 py-1 text-[10px] font-bold bg-amber-600 hover:bg-amber-500 text-white rounded cursor-pointer"
                  >
                    Relieve
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
