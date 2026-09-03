import React from 'react';
import { useShiftStore } from '../core/store';
import { getShiftBounds } from '../core/planner';

interface HeaderProps {
  currentView: 'zones' | 'equipment' | 'crew';
  onViewChange: (view: 'zones' | 'equipment' | 'crew') => void;
  onOpenWizard: () => void;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onViewChange,
  onOpenWizard,
  onOpenSettings
}) => {
  const { currentTime, isLiveTime, setLiveTime, resetShiftTo0700 } = useShiftStore();

  const now = new Date(currentTime);
  const { isDayShift } = getShiftBounds(now);
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });

  return (
    <header className="bg-slate-900 border-b border-slate-800 px-4 py-2.5 flex items-center justify-between shrink-0 select-none shadow-sm">
      {/* Left: App Title & Branding */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🚜</span>
          <div>
            <h1 className="text-base font-black text-amber-400 tracking-tight leading-none">
              ReliefScheduler
            </h1>
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Industrial Hot Seat Dispatch
            </span>
          </div>
        </div>

        {/* Shift Clock & Mode Controls */}
        <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
          <div className="px-3 py-1 bg-slate-900 rounded-lg border border-sky-500/40 text-sky-400 font-mono text-xs font-bold flex items-center gap-1.5">
            <span>🕒</span>
            <span>{timeStr}</span>
            <span className="text-[10px] font-normal text-slate-400">
              ({isDayShift ? 'Day' : 'Night'})
            </span>
          </div>

          <button
            onClick={() => setLiveTime(!isLiveTime)}
            className={`px-2 py-1 text-[11px] font-bold rounded-md transition-colors cursor-pointer ${
              isLiveTime
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle real-time clock tracking"
          >
            {isLiveTime ? '● Live' : 'Paused'}
          </button>

          <button
            onClick={resetShiftTo0700}
            className="px-2 py-1 text-[11px] font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md border border-slate-750 cursor-pointer"
            title="Jump to 07:00 (Shift Start)"
          >
            ⏮ 07:00
          </button>
        </div>
      </div>

      {/* Center: View Navigation Tabs */}
      <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
        {[
          { id: 'zones' as const, label: '📍 Pit & Zones' },
          { id: 'equipment' as const, label: '🚜 Equipment' },
          { id: 'crew' as const, label: '👥 Crew Roster' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => onViewChange(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              currentView === tab.id
                ? 'bg-slate-800 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Right: Primary Shift Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenWizard}
          className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-lg border border-emerald-400/30 flex items-center gap-1.5 transition-all cursor-pointer"
        >
          <span>🎯</span> Daily Setup Wizard
        </button>

        <button
          onClick={onOpenSettings}
          className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl border border-slate-750 transition-colors cursor-pointer"
          title="Settings and Backup"
        >
          ⚙️
        </button>
      </div>
    </header>
  );
};
