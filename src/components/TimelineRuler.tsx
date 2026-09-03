import React from 'react';
import { getShiftBounds } from '../core/planner';

interface TimelineRulerProps {
  currentTime: Date;
}

export const TimelineRuler: React.FC<TimelineRulerProps> = ({ currentTime }) => {
  const { shiftStart, shiftEnd } = getShiftBounds(currentTime);
  const totalDurationMs = shiftEnd.getTime() - shiftStart.getTime();

  const hours: Date[] = [];
  for (let i = 0; i <= 12; i++) {
    hours.push(new Date(shiftStart.getTime() + i * 3600 * 1000));
  }

  const currentProgressPct = Math.min(
    100,
    Math.max(0, ((currentTime.getTime() - shiftStart.getTime()) / totalDurationMs) * 100)
  );

  return (
    <div className="relative h-7 w-full border-b border-slate-700 select-none bg-slate-900/60 rounded-t">
      {/* Hour ticks and labels */}
      {hours.map((hourDate, i) => {
        const pct = (i / 12) * 100;
        const timeStr = hourDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        let alignClass = '-translate-x-1/2 text-center';
        if (i === 0) alignClass = 'translate-x-0 text-left pl-1';
        if (i === 12) alignClass = '-translate-x-full text-right pr-1';

        return (
          <div
            key={i}
            className="absolute top-0 bottom-0 pointer-events-none"
            style={{ left: `${pct}%` }}
          >
            <div className="w-[1px] h-2 bg-slate-600 absolute bottom-0" />
            <span className={`absolute top-0 text-[10px] font-semibold text-slate-400 font-mono ${alignClass}`}>
              {timeStr}
            </span>
          </div>
        );
      })}

      {/* Current Time Needle Pointer */}
      <div
        className="absolute bottom-0 z-20 transition-all duration-300 pointer-events-none"
        style={{ left: `${currentProgressPct}%` }}
      >
        <div className="w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[6px] border-t-red-500 -translate-x-1/2 absolute bottom-0" />
      </div>
    </div>
  );
};
