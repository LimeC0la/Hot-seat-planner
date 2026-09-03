import React, { useState } from 'react';
import { useShiftStore } from '../core/store';
import { formatShortName } from '../core/planner';

interface AllocationWizardProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AllocationWizard: React.FC<AllocationWizardProps> = ({ isOpen, onClose }) => {
  const { appState, applyDailyAllocation, setDozerRole } = useShiftStore();

  const [step, setStep] = useState<number>(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [absentOps, setAbsentOps] = useState<Set<string>>(
    new Set(appState.operators.filter(o => o.status === 'absent').map(o => o.name))
  );

  // Machine -> Operator name mapping
  const [allocations, setAllocations] = useState<Record<string, string | null>>(() => {
    const init: Record<string, string | null> = {};
    for (const m of appState.machines) {
      init[m.name] = m.currentOperatorId;
    }
    return init;
  });

  const [notRequiredMachines, setNotRequiredMachines] = useState<Set<string>>(
    new Set(appState.machines.filter(m => m.status === 'not_required').map(m => m.name))
  );

  const [resetClock, setResetClock] = useState(true);

  if (!isOpen) return null;

  const allOperators = appState.operators;
  const allMachines = appState.machines;

  // Filter present operators
  const presentOperators = allOperators.filter(o => !absentOps.has(o.name));
  const assignedOpNames = new Set(Object.values(allocations).filter(Boolean) as string[]);
  const availableSpares = presentOperators.filter(o => !assignedOpNames.has(o.name));

  // Machine category splits
  const keyMachines = allMachines.filter(
    m => m.type.includes('Digger') || m.type.includes('Excavator') || m.type.includes('Loader') || m.type.includes('Dozer')
  );
  const truckMachines = allMachines.filter(m => m.type.includes('Truck'));

  // Handlers
  const toggleAbsent = (name: string) => {
    const next = new Set(absentOps);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
      // Remove any machine assignment
      const nextAlloc = { ...allocations };
      for (const [mName, opName] of Object.entries(nextAlloc)) {
        if (opName === name) nextAlloc[mName] = null;
      }
      setAllocations(nextAlloc);
    }
    setAbsentOps(next);
  };

  const autoFillTrucks = () => {
    const nextAlloc = { ...allocations };
    const currentAssigned = new Set(Object.values(nextAlloc).filter(Boolean) as string[]);

    // Find truck drivers available
    const availableDrivers = presentOperators.filter(
      o => o.qualifications.includes('Truck') && !currentAssigned.has(o.name)
    );

    let driverIdx = 0;
    for (const m of truckMachines) {
      if (notRequiredMachines.has(m.name)) continue;
      if (!nextAlloc[m.name] && driverIdx < availableDrivers.length) {
        nextAlloc[m.name] = availableDrivers[driverIdx].name;
        driverIdx++;
      }
    }

    setAllocations(nextAlloc);
  };

  const handleApply = () => {
    applyDailyAllocation({
      allocations,
      absentOperators: Array.from(absentOps),
      notRequiredMachines: Array.from(notRequiredMachines),
      resetShiftTime: resetClock
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="bg-slate-900 border border-slate-750 w-full max-w-3xl rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Wizard Header */}
        <div className="p-4 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <h2 className="text-lg font-bold text-slate-100">Daily Shift Allocation Wizard</h2>
              <p className="text-xs text-slate-400">Configure attendance and dispatch equipment for the upcoming shift</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Step Indicator Tabs */}
        <div className="px-6 py-3 bg-slate-900/60 border-b border-slate-800 flex items-center gap-2 text-xs font-semibold">
          {[
            { num: 1, label: 'Attendance & Leave' },
            { num: 2, label: 'Key Machinery' },
            { num: 3, label: 'Haul Fleet & Review' }
          ].map(s => (
            <button
              key={s.num}
              onClick={() => setStep(s.num)}
              className={`px-3 py-1.5 rounded-lg transition-colors cursor-pointer ${
                step === s.num
                  ? 'bg-sky-600 text-white shadow'
                  : step > s.num
                  ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {s.num}. {s.label}
            </button>
          ))}
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* STEP 1: Attendance */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200">Step 1: Crew Attendance & Sick Leave</h3>
                  <p className="text-xs text-slate-400">Mark operators absent or on leave today. Absent crew will be excluded from machines.</p>
                </div>
                <button
                  onClick={() => setAbsentOps(new Set())}
                  className="px-3 py-1 text-xs font-bold bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg shadow"
                >
                  Mark All Present
                </button>
              </div>

              {/* Attendance Banner */}
              <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 flex items-center justify-around text-xs font-medium">
                <span className="text-emerald-400">✅ Present Today: <strong>{presentOperators.length}</strong></span>
                <span className="text-slate-600">|</span>
                <span className="text-rose-400">🏖 Absent / Leave: <strong>{absentOps.size}</strong></span>
                <span className="text-slate-600">|</span>
                <span className="text-slate-300">Total Roster: <strong>{allOperators.length}</strong></span>
              </div>

              {/* Search input */}
              <input
                type="text"
                placeholder="🔍 Filter operator name or qualification (e.g. Digger, Nathan)..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full px-3 py-2 text-sm bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />

              {/* Operator Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
                {allOperators
                  .filter(o => o.name.toLowerCase().includes(searchQuery.toLowerCase()) || o.qualifications.some(q => q.toLowerCase().includes(searchQuery.toLowerCase())))
                  .map(op => {
                    const isAbsent = absentOps.has(op.name);
                    return (
                      <div
                        key={op.id}
                        onClick={() => toggleAbsent(op.name)}
                        className={`p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                          isAbsent
                            ? 'bg-rose-950/20 border-rose-900/40 text-slate-400 opacity-60'
                            : 'bg-slate-850 border-slate-750 hover:border-sky-500/60'
                        }`}
                      >
                        <div className="min-w-0 pr-2">
                          <div className="text-sm font-bold text-slate-200 truncate">{op.name}</div>
                          <div className="text-[11px] text-slate-400 truncate">{op.qualifications.join(', ')}</div>
                        </div>
                        <span
                          className={`px-2 py-1 text-xs font-bold rounded ${
                            isAbsent ? 'bg-rose-900/60 text-rose-300' : 'bg-emerald-900/60 text-emerald-300'
                          }`}
                        >
                          {isAbsent ? 'Absent' : 'Present'}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* STEP 2: Key Equipment (Diggers, Loaders, Dozers) */}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-200">Step 2: Key Excavator & Dozer Staffing</h3>
                <p className="text-xs text-slate-400">Assign primary qualified operators to high-priority diggers and earthmoving machines.</p>
              </div>

              <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {keyMachines.map(m => {
                  const assignedOp = allocations[m.name] || '';
                  const isNR = notRequiredMachines.has(m.name);

                  // Qualified operators present
                  const qualifiedOps = presentOperators.filter(o => o.qualifications.includes(m.type));

                  return (
                    <div
                      key={m.id}
                      className="p-3 bg-slate-850 border border-slate-750 rounded-xl flex items-center justify-between gap-4"
                    >
                      <div className="w-40 shrink-0">
                        <div className="text-sm font-bold text-slate-200">{m.name}</div>
                        <div className="text-xs text-slate-400">{m.type} {m.zoneId && `• ${m.zoneId}`}</div>
                      </div>

                      <div className="flex-1">
                        <select
                          disabled={isNR}
                          value={assignedOp}
                          onChange={e => {
                            setAllocations({
                              ...allocations,
                              [m.name]: e.target.value || null
                            });
                          }}
                          className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:border-sky-500"
                        >
                          <option value="">-- Unassigned --</option>
                          {qualifiedOps.map(o => (
                            <option key={o.id} value={o.name}>
                              {o.name} {assignedOpNames.has(o.name) && o.name !== assignedOp ? '(Already Assigned)' : ''}
                            </option>
                          ))}
                        </select>
                      </div>

                      {m.type.toLowerCase().includes('dozer') && (
                        <button
                          type="button"
                          onClick={() => setDozerRole(m.name, m.dozerRole === 'dump' ? 'pit' : 'dump')}
                          className={`px-2 py-1 text-xs font-bold rounded border ${
                            m.dozerRole === 'dump'
                              ? 'bg-amber-950 text-amber-300 border-amber-700'
                              : 'bg-sky-950 text-sky-300 border-sky-700'
                          }`}
                          title={
                            m.dozerRole === 'dump'
                              ? 'Dump Dozer: continuous tip head operation'
                              : 'Pit Dozer: shares Light Vehicle to crib with digger'
                          }
                        >
                          {m.dozerRole === 'dump' ? '⛰️ Dump' : '🚜 Pit'}
                        </button>
                      )}

                      <button
                        onClick={() => {
                          const next = new Set(notRequiredMachines);
                          if (next.has(m.name)) next.delete(m.name);
                          else next.add(m.name);
                          setNotRequiredMachines(next);
                        }}
                        className={`px-2.5 py-1 text-xs font-semibold rounded ${
                          isNR ? 'bg-amber-900/60 text-amber-300 border border-amber-700' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {isNR ? 'Parked' : 'Operational'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* STEP 3: Haul Fleet & Review */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200">Step 3: Haul Fleet Auto-Fill & Shift Review</h3>
                  <p className="text-xs text-slate-400">Fill the haul truck fleet with remaining drivers and review the relief floater pool.</p>
                </div>
                <button
                  onClick={autoFillTrucks}
                  className="px-3.5 py-1.5 text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shadow cursor-pointer flex items-center gap-1.5"
                >
                  <span>⚡</span> Auto-Fill Remaining Trucks
                </button>
              </div>

              {/* Roster & Relief Pool Summary */}
              <div className="p-4 bg-slate-850 rounded-xl border border-slate-800 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-300">
                  Relief Floater Pool ({availableSpares.length} Available)
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {availableSpares.length === 0 ? (
                    <span className="text-xs text-slate-500 italic">No spare floaters (Shift will operate in Synchronized Crib mode)</span>
                  ) : (
                    availableSpares.map(op => (
                      <span
                        key={op.id}
                        className="px-2.5 py-1 text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/60 rounded-lg"
                      >
                        {formatShortName(op.name)} ({op.qualifications.join('/')})
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Shift Options */}
              <div className="p-3 bg-slate-850 rounded-xl border border-slate-800 flex items-center gap-3">
                <input
                  type="checkbox"
                  id="resetClockCb"
                  checked={resetClock}
                  onChange={e => setResetClock(e.target.checked)}
                  className="w-4 h-4 text-sky-600 rounded bg-slate-900 border-slate-700"
                />
                <label htmlFor="resetClockCb" className="text-xs text-slate-300 font-medium cursor-pointer">
                  Reset Shift Clock to 07:00 (Shift Start) and initialize fresh break tracking
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Wizard Footer */}
        <div className="p-4 bg-slate-850 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={() => setStep(prev => Math.max(1, prev - 1))}
            disabled={step === 1}
            className="px-4 py-2 text-xs font-bold bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 rounded-lg"
          >
            ‹ Back
          </button>

          <div className="flex gap-2">
            {step < 3 ? (
              <button
                onClick={() => setStep(prev => Math.min(3, prev + 1))}
                className="px-5 py-2 text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shadow cursor-pointer"
              >
                Next Step ›
              </button>
            ) : (
              <button
                onClick={handleApply}
                className="px-6 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-lg cursor-pointer flex items-center gap-1.5"
              >
                <span>🚀</span> Apply & Start Shift
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
