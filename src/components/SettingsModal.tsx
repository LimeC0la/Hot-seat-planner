import React, { useState } from 'react';
import { AppState, EquipmentType, Qualification } from '../types';
import { X, Trash2, Plus } from 'lucide-react';
import { cn } from './ATBQueue';

interface SettingsModalProps {
  state: AppState;
  onClose: () => void;
  onUpdateState: (newState: AppState) => void;
  onAddOperator: (name: string, qualifications: Qualification[]) => Promise<AppState>;
  onDeleteOperator: (id: string) => Promise<AppState>;
  onAddMachine: (name: string, type: EquipmentType, zoneId: string, transitTimeMinutes: number) => Promise<AppState>;
  onDeleteMachine: (id: string) => Promise<AppState>;
  onAddZone: (name: string) => Promise<AppState>;
  onDeleteZone: (id: string) => Promise<AppState>;
}

export function SettingsModal({
  state, onClose, onUpdateState,
  onAddOperator, onDeleteOperator,
  onAddMachine, onDeleteMachine,
  onAddZone, onDeleteZone
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<'operators' | 'equipment' | 'locations'>('operators');
  const [loading, setLoading] = useState(false);

  // Operator Form State
  const [opName, setOpName] = useState('');
  const [opQuals, setOpQuals] = useState<Qualification[]>([]);

  // Machine Form State
  const [macName, setMacName] = useState('');
  const [macType, setMacType] = useState<EquipmentType>('Truck');
  const [macZoneId, setMacZoneId] = useState(state.zones[0]?.id || '');
  const [macTransit, setMacTransit] = useState(10);

  // Zone Form State
  const [zoneName, setZoneName] = useState('');

  const handleAddOperator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opName || opQuals.length === 0) return;
    setLoading(true);
    try {
      const s = await onAddOperator(opName, opQuals);
      onUpdateState(s);
      setOpName('');
      setOpQuals([]);
    } finally { setLoading(false); }
  };

  const handleAddMachine = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!macName || !macZoneId) return;
    setLoading(true);
    try {
      const s = await onAddMachine(macName, macType, macZoneId, macTransit);
      onUpdateState(s);
      setMacName('');
      setMacTransit(10);
    } finally { setLoading(false); }
  };

  const handleAddZone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zoneName) return;
    setLoading(true);
    try {
      const s = await onAddZone(zoneName);
      onUpdateState(s);
      setZoneName('');
      if (!macZoneId) setMacZoneId(s.zones[0]?.id || '');
    } finally { setLoading(false); }
  };

  const toggleQual = (q: Qualification) => {
    setOpQuals(prev => prev.includes(q) ? prev.filter(x => x !== q) : [...prev, q]);
  };

  const EQUIPMENT_TYPES: EquipmentType[] = ['Truck', 'Digger', 'Auxiliary', 'ROM Loader'];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-3xl flex flex-col max-h-[85vh] shadow-2xl">
        <div className="flex justify-between items-center p-4 border-b border-slate-800">
          <h2 className="text-xl font-bold text-slate-100">Settings Manager</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors p-1 rounded hover:bg-slate-800">
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <div className="flex border-b border-slate-800 px-4 pt-2">
          {(['operators', 'equipment', 'locations'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-2 font-medium capitalize text-sm transition-colors border-b-2",
                activeTab === tab ? "border-amber-500 text-amber-500" : "border-transparent text-slate-400 hover:text-slate-200"
              )}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="p-4 overflow-y-auto flex-1">
          {activeTab === 'operators' && (
            <div className="space-y-6">
              <form onSubmit={handleAddOperator} className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2"><Plus className="w-4 h-4 text-emerald-400"/> Add Operator</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Name</label>
                    <input type="text" required value={opName} onChange={e => setOpName(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500" placeholder="e.g. Jane Doe" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Qualifications</label>
                    <div className="flex flex-wrap gap-2">
                      {EQUIPMENT_TYPES.map(q => (
                        <button type="button" key={q} onClick={() => toggleQual(q)} className={cn("text-xs px-2 py-1 rounded border", opQuals.includes(q) ? "bg-amber-500/20 border-amber-500/50 text-amber-400" : "bg-slate-900 border-slate-700 text-slate-400 hover:bg-slate-800")}>
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <button disabled={loading} type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-1.5 rounded transition-colors disabled:opacity-50">Add Operator</button>
                </div>
              </form>
              <div>
                <h3 className="font-semibold text-slate-200 mb-3">Existing Operators</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {state.operators.map(op => (
                    <div key={op.id} className="flex justify-between items-center bg-slate-800/30 p-2 rounded border border-slate-700/50">
                      <div>
                        <div className="text-sm font-medium text-slate-200">{op.name}</div>
                        <div className="text-[10px] text-slate-400">{op.qualifications.join(', ')}</div>
                      </div>
                      <button onClick={async () => { setLoading(true); try { onUpdateState(await onDeleteOperator(op.id)); } finally { setLoading(false); } }} className="text-red-400 hover:text-red-300 hover:bg-red-950 p-1.5 rounded transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'equipment' && (
            <div className="space-y-6">
              <form onSubmit={handleAddMachine} className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2"><Plus className="w-4 h-4 text-emerald-400"/> Add Equipment</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Name / Callsign</label>
                    <input type="text" required value={macName} onChange={e => setMacName(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500" placeholder="e.g. DT-505" />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Type</label>
                    <select value={macType} onChange={e => setMacType(e.target.value as EquipmentType)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500">
                      {EQUIPMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Location / Zone</label>
                    <select required value={macZoneId} onChange={e => setMacZoneId(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500">
                      {state.zones.map(z => <option key={z.id} value={z.id}>{z.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Transit (mins)</label>
                    <input type="number" min="0" required value={macTransit} onChange={e => setMacTransit(parseInt(e.target.value) || 0)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500" />
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <button disabled={loading || state.zones.length === 0} type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-1.5 rounded transition-colors disabled:opacity-50">Add Equipment</button>
                </div>
              </form>
              <div>
                <h3 className="font-semibold text-slate-200 mb-3">Existing Equipment</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {state.machines.map(m => (
                    <div key={m.id} className="flex justify-between items-center bg-slate-800/30 p-2 rounded border border-slate-700/50">
                      <div>
                        <div className="text-sm font-medium text-slate-200">{m.name}</div>
                        <div className="text-[10px] text-slate-400">{m.type} • {state.zones.find(z => z.id === m.zoneId)?.name || 'Unknown'} • {m.transitTimeMinutes}m</div>
                      </div>
                      <button onClick={async () => { setLoading(true); try { onUpdateState(await onDeleteMachine(m.id)); } finally { setLoading(false); } }} className="text-red-400 hover:text-red-300 hover:bg-red-950 p-1.5 rounded transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'locations' && (
            <div className="space-y-6">
              <form onSubmit={handleAddZone} className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2"><Plus className="w-4 h-4 text-emerald-400"/> Add Location</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Zone Name</label>
                    <input type="text" required value={zoneName} onChange={e => setZoneName(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-amber-500" placeholder="e.g. West Pit" />
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <button disabled={loading} type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-1.5 rounded transition-colors disabled:opacity-50">Add Location</button>
                </div>
              </form>
              <div>
                <h3 className="font-semibold text-slate-200 mb-3">Existing Locations</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {state.zones.map(z => (
                    <div key={z.id} className="flex justify-between items-center bg-slate-800/30 p-2 rounded border border-slate-700/50">
                      <div className="text-sm font-medium text-slate-200">{z.name}</div>
                      <button onClick={async () => { setLoading(true); try { onUpdateState(await onDeleteZone(z.id)); } finally { setLoading(false); } }} className="text-red-400 hover:text-red-300 hover:bg-red-950 p-1.5 rounded transition-colors"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
