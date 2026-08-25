import { Machine, Operator } from '../types';
import { cn } from './ATBQueue';
import { ShieldAlert, Truck, Timer, UserCircle } from 'lucide-react';

interface MachineCardProps {
  machine: Machine;
  currentOperator?: Operator;
  onAssign: (operatorId: string, machineId: string) => void;
  onBreak: (operatorId: string) => void;
}

export function MachineCard({ machine, currentOperator, onAssign, onBreak }: MachineCardProps) {
  const isBlastExclusion = machine.status === 'blast_exclusion';

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!isBlastExclusion) {
      e.dataTransfer.dropEffect = 'move';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (isBlastExclusion) return;
    
    const operatorId = e.dataTransfer.getData('operatorId');
    if (operatorId) {
      onAssign(operatorId, machine.id);
    }
  };

  return (
    <div 
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={cn(
        "relative rounded-xl border p-4 flex flex-col h-40 transition-colors duration-200",
        isBlastExclusion 
          ? "bg-red-950/20 border-red-900/50" 
          : "bg-slate-800 border-slate-700 hover:border-slate-500",
        !currentOperator && !isBlastExclusion && "border-dashed border-2 border-slate-600 bg-slate-800/50"
      )}
    >
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-bold text-slate-100 flex items-center gap-2">
            <Truck className="w-4 h-4 text-slate-400" />
            {machine.name}
          </h3>
          <span className="text-[10px] uppercase tracking-wider text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded mt-1 inline-block">
            {machine.type}
          </span>
        </div>
        {isBlastExclusion && (
          <div className="bg-red-500/10 text-red-500 p-1.5 rounded-full animate-pulse">
            <ShieldAlert className="w-4 h-4" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 flex items-end">
        {isBlastExclusion ? (
          <div className="w-full text-center text-sm font-medium text-red-400 bg-red-950/30 py-2 rounded">
            BLAST EXCLUSION
          </div>
        ) : currentOperator ? (
          <div className="w-full bg-slate-900/50 rounded-lg p-2 border border-slate-700/50 flex justify-between items-center group">
            <div className="flex items-center gap-2 text-slate-200">
              <UserCircle className="w-5 h-5 text-emerald-400" />
              <span className="font-medium text-sm">{currentOperator.name}</span>
            </div>
            <button 
              onClick={() => onBreak(currentOperator.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs px-2 py-1 rounded flex items-center gap-1"
              title={`Send on break. Transit: ${machine.transitTimeMinutes}m`}
            >
              <Timer className="w-3 h-3" />
              Relieve
            </button>
          </div>
        ) : (
          <div className="w-full text-center text-sm text-slate-500 uppercase tracking-widest py-2">
            Drop to Assign
          </div>
        )}
      </div>
    </div>
  );
}
