import React, { useState } from 'react';
import { useShiftStore } from '../core/store';
import { Machine } from '../core/types';
import { getShiftBounds, formatShortName } from '../core/planner';

interface PreassignHotseatModalProps {
  machine: Machine | null;
  isOpen: boolean;
  onClose: () => void;
}

export const PreassignHotseatModal: React.FC<PreassignHotseatModalProps> = ({
  machine,
  isOpen,
  onClose
}) => {
  const { appState, currentTime, preassignHotseat, removeHotseatLock } = useShiftStore();

  if (!isOpen || !machine) return null;

  const now = new Date(currentTime);
  const { shiftStart } = getShiftBounds(now);

  const existingLock = (appState.manualReliefs || []).find(
    l => l.machineName === machine.name && l.locked
  );

  // Available operators who are present
  const presentOps = appState.operators.filter(o => o.status !== 'absent');
  const qualifiedOps = presentOps.filter(o =>
    o.qualifications.includes(machine.type) || machine.type.toLowerCase() === 'other'
  );

  // Default times: next round 30 min window
  const defaultStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    now.getHours(),
    now.getMinutes() >= 30 ? 0 : 30,
    0
  );
  if (now.getMinutes() >= 30) {
    defaultStart.setHours(defaultStart.getHours() + 1);
  }

  const formatTimeInput = (d: Date) => {
    const h = d.getHours().toString().padStart(2, '0');
    const m = d.getMinutes().toString().padStart(2, '0');
    return `${h}:${m}`;
  };

  const [selectedOp, setSelectedOp] = useState<string>(() => {
    if (existingLock) return existingLock.reliefOperatorName;
    return qualifiedOps[0]?.name || presentOps[0]?.name || '';
  });

  const [startTimeStr, setStartTimeStr] = useState<string>(() => {
    if (existingLock) {
      return formatTimeInput(new Date(existingLock.startTime));
    }
    return formatTimeInput(defaultStart);
  });

  const [durationMins, setDurationMins] = useState<number>(30);

  const handleSave = () => {
    if (!selectedOp) return;

    // Construct full ISO strings for the shift date
    const [sH, sM] = startTimeStr.split(':').map(Number);
    const startDate = new Date(shiftStart);
    startDate.setHours(sH, sM, 0, 0);

    const endDate = new Date(startDate.getTime() + durationMins * 60 * 1000);

    preassignHotseat({
      machineName: machine.name,
      reliefOperatorName: selectedOp,
      startTime: startDate.toISOString(),
      endTime: endDate.toISOString()
    });

    onClose();
  };

  const handleUnlock = () => {
    if (existingLock) {
      removeHotseatLock(existingLock.id);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-750 w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🔒</span>
            <div>
              <h3 className="text-sm font-bold text-slate-100">
                Preassign Hotseat Relief for {machine.name}
              </h3>
              <p className="text-xs text-slate-400">
                Lock in a specific skilled relief operator and time window
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <div className="p-5 space-y-4 text-xs">
          {/* Machine Info */}
          <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-750 flex items-center justify-between">
            <div>
              <span className="text-slate-400 block text-[11px]">Machine & Type:</span>
              <span className="font-bold text-slate-200 text-sm">
                {machine.name} ({machine.type})
              </span>
            </div>
            <div className="text-right">
              <span className="text-slate-400 block text-[11px]">Current Primary Driver:</span>
              <span className="font-semibold text-sky-300">
                {machine.currentOperatorId ? formatShortName(machine.currentOperatorId) : 'None'}
              </span>
            </div>
          </div>

          {/* Operator Selection */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-300 block">
              Relief Operator (Who takes the cab?):
            </label>
            <select
              value={selectedOp}
              onChange={e => setSelectedOp(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-sky-500 font-medium"
            >
              <optgroup label="⭐ Qualified for this machine type">
                {qualifiedOps.map(op => (
                  <option key={op.id} value={op.name}>
                    {op.name} ({op.qualifications.join(', ')})
                  </option>
                ))}
              </optgroup>
              <optgroup label="Other Present Crew">
                {presentOps
                  .filter(o => !qualifiedOps.some(q => q.id === o.id))
                  .map(op => (
                    <option key={op.id} value={op.name}>
                      {op.name} ({op.qualifications.join(', ')})
                    </option>
                  ))}
              </optgroup>
            </select>
          </div>

          {/* Time & Duration */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="font-semibold text-slate-300 block">Relief Start Time:</label>
              <input
                type="time"
                value={startTimeStr}
                onChange={e => setStartTimeStr(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:border-sky-500 text-center font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-semibold text-slate-300 block">Duration (Minutes):</label>
              <select
                value={durationMins}
                onChange={e => setDurationMins(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:border-sky-500"
              >
                <option value={20}>20 minutes</option>
                <option value={30}>30 minutes (Standard)</option>
                <option value={45}>45 minutes</option>
                <option value={60}>60 minutes</option>
              </select>
            </div>
          </div>

          {/* Current Lock Status info */}
          {existingLock && (
            <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl text-amber-300 flex items-center justify-between">
              <div>
                <span className="font-bold block">Current Active Lock</span>
                <span className="text-[11px] text-amber-200/80">
                  {existingLock.reliefOperatorName} (
                  {new Date(existingLock.startTime).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}{' '}
                  -{' '}
                  {new Date(existingLock.endTime).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                  )
                </span>
              </div>
              <button
                onClick={handleUnlock}
                className="px-2.5 py-1 text-xs bg-rose-900/80 hover:bg-rose-800 text-rose-200 rounded-lg font-bold"
              >
                Remove Lock
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-850 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shadow-lg cursor-pointer flex items-center gap-1.5"
          >
            <span>🔒</span>
            <span>Lock Hotseat Assignment</span>
          </button>
        </div>
      </div>
    </div>
  );
};
