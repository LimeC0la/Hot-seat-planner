import { AppState, ViewMode } from '../types';
import { MachineCard } from './MachineCard';
import { cn } from './ATBQueue';

interface FloorViewProps {
  state: AppState;
  viewMode: ViewMode;
  onAssign: (operatorId: string, machineId: string) => void;
  onBreak: (operatorId: string) => void;
}

export function FloorView({ state, viewMode, onAssign, onBreak }: FloorViewProps) {
  const renderZoneView = () => {
    return state.zones.map(zone => {
      const zoneMachines = state.machines.filter(m => m.zoneId === zone.id);
      
      return (
        <div key={zone.id} className={cn(
          "mb-8 rounded-2xl border p-6 transition-colors duration-300",
          zone.hasActiveBlast ? "border-red-900/50 bg-red-950/10" : "border-slate-800 bg-slate-900/30"
        )}>
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold text-slate-200">{zone.name}</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {zoneMachines.map(machine => (
              <MachineCard
                key={machine.id}
                machine={machine}
                currentOperator={state.operators.find(o => o.id === machine.currentOperatorId)}
                onAssign={onAssign}
                onBreak={onBreak}
              />
            ))}
            {zoneMachines.length === 0 && (
              <div className="text-slate-500 text-sm col-span-full">No machines in this zone.</div>
            )}
          </div>
        </div>
      );
    });
  };

  const renderEquipmentView = () => {
    const types = Array.from(new Set(state.machines.map(m => m.type)));

    return types.map(type => {
      const typeMachines = state.machines.filter(m => m.type === type);
      
      return (
        <div key={type} className="mb-8 rounded-2xl border border-slate-800 bg-slate-900/30 p-6">
          <h2 className="text-xl font-bold text-slate-200 mb-6">{type}s</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {typeMachines.map(machine => (
              <MachineCard
                key={machine.id}
                machine={machine}
                currentOperator={state.operators.find(o => o.id === machine.currentOperatorId)}
                onAssign={onAssign}
                onBreak={onBreak}
              />
            ))}
          </div>
        </div>
      );
    });
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-7xl mx-auto">
        {viewMode === 'zone' ? renderZoneView() : renderEquipmentView()}
      </div>
    </div>
  );
}
