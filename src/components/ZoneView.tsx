import React from 'react';
import { useShiftStore } from '../core/store';
import { TimelineRuler } from './TimelineRuler';
import { TimelineTrack } from './TimelineTrack';
import { formatShortName } from '../core/planner';
import { Machine } from '../core/types';

export const ZoneView: React.FC = () => {
  const {
    appState,
    currentTime,
    sendOnBreak,
    relieveOperatorOnMachine,
    setMachineStatus,
    assignOperator
  } = useShiftStore();

  const now = new Date(currentTime);
  const zones = appState.zones;
  const machines = appState.machines;
  const operators = appState.operators;
  const plannedSegments = appState.plannedSegments;

  // Find standby operators who can act as relief
  const standbyOps = operators.filter(o => o.status === 'standby');

  const getMachineSegments = (machineName: string) => {
    return plannedSegments.filter(s => s.machineName === machineName);
  };

  const getPendingReliefOp = (m: Machine): string | null => {
    if (!m.currentOperatorId) return null;
    // Check if there is a planned relief segment in progress or starting soon
    const segs = getMachineSegments(m.name);
    const currentRelief = segs.find(s => {
      const sStart = new Date(s.startTime);
      const sEnd = new Date(s.endTime);
      return (
        s.segmentType === 'assignment' &&
        s.operatorName !== m.currentOperatorId &&
        now >= new Date(sStart.getTime() - 10 * 60 * 1000) &&
        now <= sEnd
      );
    });

    if (currentRelief) return currentRelief.operatorName;

    // Or fallback to first qualified standby
    const qualifiedStandby = standbyOps.find(o => o.qualifications.includes(m.type));
    return qualifiedStandby ? qualifiedStandby.name : null;
  };

  // Group machines by zone
  const knownZoneIds = new Set(zones.map(z => z.name));
  const zoneGroups = zones.map(z => ({
    zone: z,
    machines: machines.filter(m => m.zoneId === z.name || m.zoneId === z.id)
  }));

  const unassignedMachines = machines.filter(m => !m.zoneId || !knownZoneIds.has(m.zoneId));

  return (
    <div className="space-y-6">
      {zoneGroups.map(({ zone, machines: zoneMachines }) => (
        <div
          key={zone.id}
          className="bg-slate-900 border border-slate-800 rounded-xl shadow-md overflow-hidden"
        >
          {/* Zone Header */}
          <div className="px-4 py-3 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">📍</span>
              <h2 className="text-base font-bold text-slate-100 tracking-wide">{zone.name}</h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-slate-800 text-slate-400 rounded-full border border-slate-700">
                {zoneMachines.length} units
              </span>
            </div>
            {zone.hasActiveBlast && (
              <span className="px-2.5 py-1 text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 rounded-md animate-pulse">
                ⚠️ Blast Exclusion Active
              </span>
            )}
          </div>

          {/* Section Body */}
          <div className="p-3 space-y-2">
            {/* Shared Ruler */}
            <div className="flex items-center gap-3 px-2">
              <div className="w-56 shrink-0 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
                Equipment & Crew
              </div>
              <div className="flex-1">
                <TimelineRuler currentTime={now} />
              </div>
            </div>

            {/* Machines Stack */}
            {zoneMachines.length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-500 italic bg-slate-950/30 rounded-lg border border-dashed border-slate-800">
                No equipment assigned to {zone.name}
              </div>
            ) : (
              zoneMachines.map(m => {
                const isNR = m.status === 'not_required';
                const isMaint = m.status === 'maintenance';
                const currentOp = operators.find(o => o.name === m.currentOperatorId);
                const pendingRelief = getPendingReliefOp(m);
                const segs = getMachineSegments(m.name);

                return (
                  <div
                    key={m.id}
                    className={`flex items-center gap-3 p-2 rounded-lg border transition-colors ${
                      isNR
                        ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                        : isMaint
                        ? 'bg-amber-950/20 border-amber-900/40'
                        : 'bg-slate-850 border-slate-750 hover:border-slate-600'
                    }`}
                  >
                    {/* Machine info column (Width: 224px / 56) */}
                    <div className="w-56 shrink-0 flex items-center justify-between pr-2">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-black text-slate-200 tracking-tight">{m.name}</span>
                          <span className="text-[10px] text-slate-400">({m.type})</span>
                        </div>
                        <div className="text-xs font-medium text-slate-400 flex items-center gap-1">
                          {currentOp ? (
                            <span className="text-sky-300 font-semibold truncate max-w-[110px]" title={currentOp.name}>
                              👷 {formatShortName(currentOp.name)}
                            </span>
                          ) : isNR ? (
                            <span className="text-slate-500 italic text-[11px]">Parked / Off</span>
                          ) : isMaint ? (
                            <span className="text-amber-400 italic text-[11px]">Maintenance</span>
                          ) : (
                            <span className="text-rose-400 italic text-[11px]">Uncrewed</span>
                          )}
                        </div>
                      </div>

                      {/* Quick Action button */}
                      <div className="flex items-center gap-1">
                        {isNR ? (
                          <button
                            onClick={() => setMachineStatus(m.name, 'operational')}
                            className="px-2 py-1 text-[11px] font-bold bg-emerald-700 hover:bg-emerald-600 text-white rounded shadow cursor-pointer"
                            title="Activate machine"
                          >
                            Start
                          </button>
                        ) : currentOp ? (
                          <button
                            onClick={() => {
                              if (pendingRelief) {
                                relieveOperatorOnMachine(m.name, pendingRelief);
                              } else {
                                sendOnBreak(currentOp.name);
                              }
                            }}
                            className={`px-2 py-1 text-[11px] font-bold rounded shadow transition-colors cursor-pointer ${
                              pendingRelief
                                ? 'bg-amber-600 hover:bg-amber-500 text-white animate-pulse'
                                : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
                            }`}
                            title={pendingRelief ? `Relieve with ${pendingRelief}` : 'Send operator on break'}
                          >
                            {pendingRelief ? 'Relieve' : 'Break'}
                          </button>
                        ) : (
                          // Uncrewed, allow quick assign from standby
                          standbyOps.length > 0 && (
                            <button
                              onClick={() => {
                                const qualOp = standbyOps.find(o => o.qualifications.includes(m.type)) || standbyOps[0];
                                if (qualOp) assignOperator(qualOp.name, m.name);
                              }}
                              className="px-2 py-1 text-[11px] font-bold bg-sky-700 hover:bg-sky-600 text-white rounded shadow cursor-pointer"
                              title="Assign standby operator"
                            >
                              Assign
                            </button>
                          )
                        )}
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
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      ))}

      {/* Unassigned Machines if any */}
      {unassignedMachines.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-md overflow-hidden opacity-80">
          <div className="px-4 py-3 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl">📦</span>
              <h2 className="text-base font-bold text-amber-300">Unassigned / Standby Equipment</h2>
              <span className="px-2 py-0.5 text-xs font-semibold bg-slate-800 text-slate-400 rounded-full">
                {unassignedMachines.length} units
              </span>
            </div>
          </div>
          <div className="p-3 space-y-2">
            {unassignedMachines.map(m => (
              <div
                key={m.id}
                className="flex items-center justify-between p-2.5 bg-slate-850 rounded-lg border border-slate-800"
              >
                <div className="flex items-center gap-3">
                  <span className="font-bold text-slate-200">{m.name}</span>
                  <span className="text-xs text-slate-400">({m.type})</span>
                  <span className="text-xs text-slate-500">Status: {m.status}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setMachineStatus(m.name, m.status === 'operational' ? 'not_required' : 'operational')}
                    className="px-2.5 py-1 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700"
                  >
                    Toggle Operational
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
