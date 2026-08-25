import { Operator } from '../types';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Clock } from 'lucide-react';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ATBQueueProps {
  operators: Operator[];
}

export function ATBQueue({ operators }: ATBQueueProps) {
  // Sort by standby time descending, only show standby operators
  const standbyOperators = operators
    .filter(op => op.status === 'standby')
    .sort((a, b) => b.standbyTimeMinutes - a.standbyTimeMinutes);

  const MAX_WAIT = 120; // 120 minutes max expected wait time

  return (
    <div className="w-80 bg-slate-900 border-r border-slate-800 h-full flex flex-col">
      <div className="p-4 border-b border-slate-800">
        <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Clock className="w-5 h-5 text-amber-500" />
          Relief ATB Queue
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Drag operators to assign. Gauges fill over time.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {standbyOperators.map((op) => {
          const fillPercentage = Math.min((op.standbyTimeMinutes / MAX_WAIT) * 100, 100);
          const isCritical = op.standbyTimeMinutes >= 90;

          return (
            <div
              key={op.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('operatorId', op.id);
                e.dataTransfer.effectAllowed = 'move';
              }}
              className="bg-slate-800 rounded-lg p-3 cursor-grab active:cursor-grabbing border border-slate-700 hover:border-amber-500/50 transition-colors shadow-sm"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-slate-200">{op.name}</span>
                <span className={cn(
                  "text-xs font-mono px-2 py-1 rounded bg-slate-950",
                  isCritical ? "text-amber-500" : "text-slate-400"
                )}>
                  {op.standbyTimeMinutes}m wait
                </span>
              </div>
              
              <div className="flex flex-wrap gap-1 mb-3">
                {op.qualifications.map(q => (
                  <span key={q} className="text-[10px] uppercase tracking-wider bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
                    {q}
                  </span>
                ))}
              </div>

              {/* ATB Gauge */}
              <div className="h-2 w-full bg-slate-950 rounded-full overflow-hidden">
                <div 
                  className={cn(
                    "h-full transition-all duration-1000 rounded-full",
                    isCritical ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]" : "bg-emerald-500"
                  )}
                  style={{ width: `${fillPercentage}%` }}
                />
              </div>
            </div>
          );
        })}
        {standbyOperators.length === 0 && (
          <div className="text-center p-8 text-slate-500 text-sm">
            No operators on standby.
          </div>
        )}
      </div>
    </div>
  );
}
