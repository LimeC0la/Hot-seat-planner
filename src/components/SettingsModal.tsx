import React, { useState } from 'react';
import { useShiftStore } from '../core/store';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { appState, updateSettings, exportStateJson, importStateJson, resetToDefaultState } = useShiftStore();
  const settings = appState.settings;

  const [targetBreaks, setTargetBreaks] = useState(settings.targetBreaksPerShift);
  const [breakDuration, setBreakDuration] = useState(settings.breakDurationMinutes);
  const [cooldown, setCooldown] = useState(settings.breakCooldownMinutes);
  const [importError, setImportError] = useState('');

  if (!isOpen) return null;

  const handleSave = () => {
    updateSettings({
      targetBreaksPerShift: targetBreaks,
      breakDurationMinutes: breakDuration,
      breakCooldownMinutes: cooldown
    });
    onClose();
  };

  const handleExport = () => {
    const dataStr = exportStateJson();
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `hotseat_shift_backup_${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleFileImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    setImportError('');
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = event => {
      const content = event.target?.result as string;
      const success = importStateJson(content);
      if (success) {
        onClose();
      } else {
        setImportError('Invalid configuration JSON file.');
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-750 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        <div className="p-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚙️</span>
            <h2 className="text-base font-bold text-slate-100">Scheduling Rules & Data Management</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Scheduling Rules */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-sky-400">Shift Rest Rules</h3>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Target Breaks per Shift</label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={targetBreaks}
                  onChange={e => setTargetBreaks(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Break Duration (Minutes)</label>
                <input
                  type="number"
                  min={10}
                  max={60}
                  step={5}
                  value={breakDuration}
                  onChange={e => setBreakDuration(parseInt(e.target.value) || 30)}
                  className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100"
                />
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-300 mb-1">Break Cooldown (Minutes between breaks)</label>
                <input
                  type="number"
                  min={30}
                  max={240}
                  step={15}
                  value={cooldown}
                  onChange={e => setCooldown(parseInt(e.target.value) || 90)}
                  className="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-100"
                />
                <p className="text-[11px] text-slate-500 mt-1">Minimum operating interval before the same operator can take another break.</p>
              </div>
            </div>
          </div>

          <hr className="border-slate-800" />

          {/* Backup & Restore */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-400">Backup & Data Portability</h3>
            <p className="text-xs text-slate-400">Export your fleet and roster state to JSON or load an existing configuration.</p>

            <div className="flex gap-2">
              <button
                onClick={handleExport}
                className="flex-1 py-2 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>📥</span> Export JSON Backup
              </button>

              <label className="flex-1 py-2 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 flex items-center justify-center gap-1.5 cursor-pointer text-center">
                <span>📤</span> Import JSON
                <input type="file" accept=".json" onChange={handleFileImport} className="hidden" />
              </label>
            </div>

            {importError && <p className="text-xs text-rose-400 font-medium">{importError}</p>}
          </div>

          <hr className="border-slate-800" />

          {/* Danger Zone */}
          <div>
            <button
              onClick={() => {
                if (confirm('Reset application back to default factory fleet and roster?')) {
                  resetToDefaultState();
                  onClose();
                }
              }}
              className="text-xs text-rose-400 hover:text-rose-300 font-semibold cursor-pointer"
            >
              ⚠️ Reset Fleet to Original Defaults
            </button>
          </div>
        </div>

        <div className="p-4 bg-slate-850 border-t border-slate-800 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shadow cursor-pointer"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};
