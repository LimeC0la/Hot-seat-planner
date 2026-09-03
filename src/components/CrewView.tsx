import React from 'react';
import { useShiftStore } from '../core/store';
import { TimelineRuler } from './TimelineRuler';
import { TimelineTrack } from './TimelineTrack';
import { formatShortName } from '../core/planner';

export const CrewView: React.FC = () => {
  const {
    appState,
    currentTime,
    sendOnBreak,
    returnFromBreak,
    setOperatorAbsent
  } = useShiftStore();

  const now = new Date(currentTime);
  const operators = appState.operators;
  const plannedSegments = appState.plannedSegments;
  const targetBreaks = appState.settings.targetBreaksPerShift;

  const activeCrew = operators.filter(o => o.status !== 'absent');
  const absentCrew = operators.filter(o => o.status === 'absent');

  return (
    <div className="space-y-6">
      {/* Active Crew Board */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-md overflow-hidden">
        <div className="px-4 py-3 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">👥</span>
            <h2 className="text-base font-bold text-slate-100">Crew Roster On Shift</h2>
            <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
              {activeCrew.length} active
            </span>
          </div>

          {/* Status legend */}
          <div className="hidden sm:flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-sky-300">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500 inline-block" /> Operating
            </span>
            <span className="flex items-center gap-1.5 text-purple-300">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block" /> Break
            </span>
            <span className="flex items-center gap-1.5 text-amber-300">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Standby / Relief
            </span>
          </div>
        </div>

        <div className="p-3 space-y-2">
          {/* Timeline Header */}
          <div className="flex items-center gap-3 px-2">
            <div className="w-64 shrink-0 text-[10px] font-bold tracking-wider text-slate-500 uppercase">
              Operator & Shift Status
            </div>
            <div className="flex-1">
              <TimelineRuler currentTime={now} />
            </div>
          </div>

          {activeCrew.map(op => {
            const opSegments = plannedSegments.filter(s => s.operatorName === op.name);
            const isWorking = op.status === 'working';
            const isOnBreak = op.status === 'on_break';
            const isStandby = op.status === 'standby';

            return (
              <div
                key={op.id}
                className="flex items-center gap-3 p-2 rounded-lg bg-slate-850 border border-slate-750 hover:border-slate-600 transition-colors"
              >
                {/* Left Column (Operator Name + Badges) */}
                <div className="w-64 shrink-0 flex items-center justify-between pr-2">
                  <div className="min-w-0 pr-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-bold text-slate-200 truncate" title={op.name}>
                        {formatShortName(op.name)}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded">
                        {op.breaksTaken}/{targetBreaks} crib
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 mt-0.5">
                      {isWorking && (
                        <span className="px-1.5 py-0.2 text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded truncate max-w-[120px]">
                          🚜 {op.currentAssignmentId || 'Operating'}
                        </span>
                      )}
                      {isOnBreak && (
                        <span className="px-1.5 py-0.2 text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded">
                          ☕ On Break
                        </span>
                      )}
                      {isStandby && (
                        <span className="px-1.5 py-0.2 text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded">
                          ⏳ Standby Floater
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0">
                    {isWorking && (
                      <button
                        onClick={() => sendOnBreak(op.name)}
                        className="px-2 py-1 text-[11px] font-bold bg-purple-700 hover:bg-purple-600 text-white rounded cursor-pointer"
                        title="Send on break now"
                      >
                        Break
                      </button>
                    )}
                    {isOnBreak && (
                      <button
                        onClick={() => returnFromBreak(op.name)}
                        className="px-2 py-1 text-[11px] font-bold bg-emerald-700 hover:bg-emerald-600 text-white rounded cursor-pointer"
                        title="Return from break to standby"
                      >
                        Return
                      </button>
                    )}
                    <button
                      onClick={() => setOperatorAbsent(op.name, true)}
                      className="px-1.5 py-1 text-[10px] text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded cursor-pointer"
                      title="Mark as absent/sick leave"
                    >
                      Leave
                    </button>
                  </div>
                </div>

                {/* Right Column: Timeline Track */}
                <div className="flex-1 min-w-0">
                  <TimelineTrack segments={opSegments} currentTime={now} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Absent Crew Section */}
      {absentCrew.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-md overflow-hidden opacity-75">
          <div className="px-4 py-2.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg">🏖</span>
              <h3 className="text-sm font-bold text-slate-300">Absent / Leave Today ({absentCrew.length})</h3>
            </div>
          </div>
          <div className="p-3 flex flex-wrap gap-2">
            {absentCrew.map(op => (
              <div
                key={op.id}
                className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-850 border border-slate-800 rounded-lg text-xs"
              >
                <span className="text-slate-400">{op.name}</span>
                <button
                  onClick={() => setOperatorAbsent(op.name, false)}
                  className="px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-900/60 hover:bg-emerald-800 text-emerald-300 border border-emerald-700/50 rounded"
                >
                  Mark Present
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
