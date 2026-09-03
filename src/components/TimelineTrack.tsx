import React from 'react';
import { PlannedSegment } from '../core/types';
import { getShiftBounds, formatShortName } from '../core/planner';

interface TimelineTrackProps {
  segments: PlannedSegment[];
  currentTime: Date;
  pendingReliefName?: string | null;
  onConfirmRelief?: () => void;
}

export const TimelineTrack: React.FC<TimelineTrackProps> = ({
  segments,
  currentTime,
  pendingReliefName,
  onConfirmRelief
}) => {
  const { shiftStart, shiftEnd } = getShiftBounds(currentTime);
  const totalMs = shiftEnd.getTime() - shiftStart.getTime();

  const currentPct = Math.min(
    100,
    Math.max(0, ((currentTime.getTime() - shiftStart.getTime()) / totalMs) * 100)
  );

  return (
    <div className="relative h-8 w-full bg-slate-950/70 rounded border border-slate-800 overflow-hidden flex items-center">
      {/* Background hour grid lines */}
      {Array.from({ length: 11 }).map((_, i) => (
        <div
          key={i}
          className="absolute top-0 bottom-0 w-[1px] bg-slate-800/40 pointer-events-none"
          style={{ left: `${((i + 1) / 12) * 100}%` }}
        />
      ))}

      {/* Render Segments */}
      {segments.map((seg, idx) => {
        const segStart = new Date(seg.startTime);
        const segEnd = new Date(seg.endTime);

        const leftPct = Math.max(0, Math.min(100, ((segStart.getTime() - shiftStart.getTime()) / totalMs) * 100));
        const rightPct = Math.max(0, Math.min(100, ((segEnd.getTime() - shiftStart.getTime()) / totalMs) * 100));
        const widthPct = Math.max(0.5, rightPct - leftPct);

        const isPast = segEnd <= currentTime;
        const isCurrent = segStart <= currentTime && segEnd > currentTime;

        let bgStyle = 'bg-sky-600/70 border-sky-400/80 text-sky-100'; // Default assignment
        if (seg.segmentType === 'break') {
          bgStyle = 'bg-purple-600/80 border-purple-400 text-purple-100';
        } else if (seg.segmentType === 'assignment' && !isPast && !isCurrent) {
          // Projected future plan
          bgStyle = 'bg-sky-950/60 border-sky-600/60 border-dashed text-sky-300';
        }

        return (
          <div
            key={idx}
            className={`absolute top-1 bottom-1 rounded border px-1.5 flex items-center justify-center text-[11px] font-medium truncate select-none shadow-sm transition-opacity hover:opacity-90 ${bgStyle}`}
            style={{
              left: `${leftPct}%`,
              width: `${widthPct}%`
            }}
            title={`${seg.operatorName} (${seg.segmentType}): ${segStart.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${segEnd.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
          >
            {widthPct > 5 && (
              <span className="truncate">
                {seg.segmentType === 'break' ? '☕ Break' : formatShortName(seg.operatorName)}
              </span>
            )}
          </div>
        );
      })}

      {/* Current Time Needle */}
      <div
        className="absolute top-0 bottom-0 w-[2px] bg-red-500 z-10 pointer-events-none"
        style={{ left: `${currentPct}%` }}
      />

      {/* Interactive Pending Relief Action Pill */}
      {pendingReliefName && onConfirmRelief && (
        <div
          className="absolute z-20 -translate-x-1/2"
          style={{ left: `${currentPct}%` }}
        >
          <button
            onClick={onConfirmRelief}
            className="px-2.5 py-1 text-xs font-bold bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-slate-950 rounded-full shadow-lg border border-amber-300 flex items-center gap-1 animate-pulse cursor-pointer"
            title={`Relieve machine with ${pendingReliefName}`}
          >
            <span>⇄ Relieve:</span>
            <span className="underline">{formatShortName(pendingReliefName)}</span>
          </button>
        </div>
      )}
    </div>
  );
};
