import React from 'react';
import { useShiftStore } from '../core/store';
import { TimelineRuler } from './TimelineRuler';
import { TimelineTrack } from './TimelineTrack';
import { formatShortName } from '../core/planner';
import { Machine } from '../core/types';

export const EquipmentView: React.FC = () => {
  const {
    appState,
    currentTime,
    sendOnBreak,
    relieveOperatorOnMachine,
    returnPrimaryOperator,
    setMachineStatus
  } = useShiftStore();

  const now = new Date(currentTime);
  const machines = appState.machines;
  const operators = appState.operators;
  const plannedSegments = appState.plannedSegments;

  const getMachineSegments = (machineName: string) => {
    return plannedSegments.filter(s => s.machineName === machineName);
  };

  const getReliefState = (m: Machine) => {
    // 1. Check if currently under active relief
    const isCurrentlyRelieved = Boolean(
      m.reliefOperatorId && m.currentOperatorId === m.reliefOperatorId
    );

    if (isCurrentlyRelieved) {
      return {
        isCurrentlyRelieved: true,
        primaryOpName: m.primaryOperatorId || null,
        reliefOpName: m.reliefOperatorId || null,
        pendingRelief: null,
        returnPrimary: m.primaryOperatorId || null
      };
    }

    // 2. Machine is operating with primary driver.
    // Check if there is a scheduled hotseat relief starting around now!
    const segs = getMachineSegments(m.name);
    const scheduled = segs.find(s => {
      if (s.segmentType !== 'assignment') return false;
      if (!s.isHotseatRelief) return false;
      if (s.operatorName === m.currentOperatorId) return false;

      const sStart = new Date(s.startTime);
      const sEnd = new Date(s.endTime);
      return now >= new Date(sStart.getTime() - 10 * 60 * 1000) && now <= sEnd;
    });

    let pendingRelief: string | null = null;
    if (scheduled) {
      const op = operators.find(o => o.name === scheduled.operatorName);
      if (op && (op.status === 'standby' || op.status === 'working')) {
        pendingRelief = scheduled.operatorName;
      }
    }

    return {
      isCurrentlyRelieved: false,
      primaryOpName: m.primaryOperatorId || m.currentOperatorId || null,
      reliefOpName: null,
      pendingRelief,
      returnPrimary: null
    };
  };

  // Distinct equipment types sorted
  const types = Array.from(new Set(machines.map(m => m.type || 'Other'))).sort();

  return (
    <div className="space-y-6">
      {types.map(machType => {
        const typeMachines = machines.filter(m => (m.type || 'Other') === machType);
        if (typeMachines.length === 0) return null;

        return (
          <div
            key={machType}
            className="bg-slate-900 border border-slate-800 rounded-xl shadow-md overflow-hidden"
          >
            {/* Category Header */}
            <div className="px-4 py-3 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xl">🚜</span>
                <h2 className="text-base font-bold text-slate-100">{machType} Fleet</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-slate-800 text-slate-400 rounded-full border border-slate-700">
                  {typeMachines.length} units
                </span>
              </div>
            </div>

            {/* Content */}
            <div className="p-3 space-y-2">
              {/* Shared Ruler Header */}
              <div className="flex items-center gap-3 px-2">
                <div className="w-56 shrink-0 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                  Machine & Operator
                </div>
                <div className="flex-1">
                  <TimelineRuler currentTime={now} />
                </div>
              </div>

              {typeMachines.map(m => {
                const isNR = m.status === 'not_required';
                const currentOp = operators.find(o => o.name === m.currentOperatorId);
                const segs = getMachineSegments(m.name);
                const { isCurrentlyRelieved, primaryOpName, reliefOpName, pendingRelief, returnPrimary } = getReliefState(m);

                return (
                  <div
                    key={m.id}
                    className={`flex items-center gap-3 p-2 rounded-lg border transition-colors ${
                      isNR
                        ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                        : 'bg-slate-850 border-slate-750 hover:border-slate-600'
                    }`}
                  >
                    {/* Machine label & driver info */}
                    <div className="w-56 shrink-0 flex items-center justify-between pr-2">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-bold text-slate-200">{m.name}</span>
                          {m.zoneId && (
                            <span className="text-[10px] px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded">
                              {m.zoneId}
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 truncate max-w-[140px]">
                          {isCurrentlyRelieved && reliefOpName ? (
                            <span
                              className="text-emerald-300 font-semibold truncate"
                              title={`Relieved by ${reliefOpName} (Primary: ${primaryOpName || 'Driver'})`}
                            >
                              ⚡ {formatShortName(reliefOpName)}{' '}
                              <span className="text-[10px] text-slate-400 font-normal">
                                ({formatShortName(primaryOpName || '')} crib)
                              </span>
                            </span>
                          ) : currentOp ? (
                            <span className="text-sky-300 font-medium truncate">
                              👷 {formatShortName(currentOp.name)}
                            </span>
                          ) : isNR ? (
                            <span className="text-slate-500 italic text-[11px]">Parked</span>
                          ) : (
                            <span className="text-rose-400 italic text-[11px]">Uncrewed</span>
                          )}
                        </div>
                      </div>

                      {/* Action */}
                      <div>
                        {isNR ? (
                          <button
                            onClick={() => setMachineStatus(m.name, 'operational')}
                            className="px-2 py-1 text-[11px] font-bold bg-emerald-700 hover:bg-emerald-600 text-white rounded cursor-pointer"
                          >
                            Start
                          </button>
                        ) : returnPrimary ? (
                          <button
                            onClick={() => returnPrimaryOperator(m.name)}
                            className="px-2 py-1 text-[11px] font-bold bg-emerald-700 hover:bg-emerald-600 text-white rounded cursor-pointer"
                            title={`Return primary operator ${returnPrimary}`}
                          >
                            Return
                          </button>
                        ) : pendingRelief ? (
                          <button
                            onClick={() => relieveOperatorOnMachine(m.name, pendingRelief)}
                            className="px-2 py-1 text-[11px] font-bold bg-amber-600 hover:bg-amber-500 text-slate-950 rounded cursor-pointer"
                            title={`Relieve machine with ${pendingRelief}`}
                          >
                            Relieve
                          </button>
                        ) : currentOp ? (
                          <button
                            onClick={() => sendOnBreak(currentOp.name)}
                            className="px-2 py-1 text-[11px] font-bold bg-slate-700 hover:bg-slate-600 text-slate-200 rounded cursor-pointer"
                          >
                            Break
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {/* Timeline track */}
                    <div className="flex-1 min-w-0">
                      <TimelineTrack
                        segments={segs}
                        currentTime={now}
                        pendingReliefName={pendingRelief}
                        onConfirmRelief={
                          pendingRelief ? () => relieveOperatorOnMachine(m.name, pendingRelief) : undefined
                        }
                        returnPrimaryName={returnPrimary}
                        onConfirmReturnPrimary={
                          returnPrimary ? () => returnPrimaryOperator(m.name) : undefined
                        }
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
};
