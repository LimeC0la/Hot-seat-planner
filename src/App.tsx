import { useEffect, useState } from 'react';
import { AppState, ViewMode } from './types';
import { fetchState, assignOperator, sendOnBreak, toggleBlast } from './utils/api';
import { ATBQueue } from './components/ATBQueue';
import { FloorView } from './components/FloorView';
import { LayoutGrid, Map, Loader2, HardHat } from 'lucide-react';
import { cn } from './components/ATBQueue';

export default function App() {
  const [state, setState] = useState<AppState | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('zone');
  const [error, setError] = useState<string | null>(null);

  const loadState = async () => {
    try {
      const data = await fetchState();
      setState(data);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Lost connection to server');
    }
  };

  useEffect(() => {
    loadState();
    const interval = setInterval(loadState, 5000); // Poll every 5s for ATB gauge updates
    return () => clearInterval(interval);
  }, []);

  const handleAssign = async (operatorId: string, machineId: string) => {
    try {
      const newState = await assignOperator(operatorId, machineId);
      setState(newState);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      setTimeout(() => setError(null), 3000);
    }
  };

  const handleBreak = async (operatorId: string) => {
    try {
      const { state: newState, travelTime } = await sendOnBreak(operatorId);
      setState(newState);
      alert(`Operator sent on break. Added ${travelTime}m transit time to interval.`);
    } catch (err: any) {
      setError(err.message);
      setTimeout(() => setError(null), 3000);
    }
  };

  const handleToggleBlast = async (zoneId: string, active: boolean) => {
    try {
      const newState = await toggleBlast(zoneId, active);
      setState(newState);
    } catch (err: any) {
      setError(err.message);
      setTimeout(() => setError(null), 3000);
    }
  };

  if (!state) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-amber-500">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col font-sans overflow-hidden">
      {/* Top Navigation */}
      <header className="h-16 border-b border-slate-800 bg-slate-900 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3 text-amber-500">
          <HardHat className="w-6 h-6" />
          <h1 className="text-xl font-bold tracking-wide">ReliefScheduler</h1>
          <span className="ml-4 px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-400 border border-slate-700">
            Shift: 06:40 - 19:30
          </span>
        </div>

        <div className="flex items-center gap-4">
          {error && (
            <div className="bg-red-500/10 text-red-400 px-4 py-1.5 rounded-full text-sm font-medium animate-pulse border border-red-500/20">
              {error}
            </div>
          )}
          <div className="flex bg-slate-800 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('zone')}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                viewMode === 'zone' ? "bg-slate-700 text-slate-100 shadow-sm" : "text-slate-400 hover:text-slate-200"
              )}
            >
              <Map className="w-4 h-4" />
              Zone View
            </button>
            <button
              onClick={() => setViewMode('equipment')}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                viewMode === 'equipment' ? "bg-slate-700 text-slate-100 shadow-sm" : "text-slate-400 hover:text-slate-200"
              )}
            >
              <LayoutGrid className="w-4 h-4" />
              Equipment View
            </button>
          </div>
        </div>
      </header>

      {/* Main Dashboard Area */}
      <main className="flex-1 flex overflow-hidden">
        <ATBQueue operators={state.operators} />
        <FloorView 
          state={state} 
          viewMode={viewMode}
          onAssign={handleAssign}
          onBreak={handleBreak}
          onToggleBlast={handleToggleBlast}
        />
      </main>
    </div>
  );
}
