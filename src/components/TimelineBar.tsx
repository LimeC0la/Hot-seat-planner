import React from 'react';

interface TimelineBarProps {
  startTime: string; // ISO timestamp
  endTime: string;   // ISO timestamp
  label: string;    // Operator name or status
}

// Simple placeholder: renders a bar with start/end times and label.
export function TimelineBar({ startTime, endTime, label }: TimelineBarProps) {
  const start = new Date(startTime);
  const end = new Date(endTime);
  const duration = isNaN(start.getTime()) || isNaN(end.getTime())
    ? 0
    : (end.getTime() - start.getTime()) / 60000;

  const width = Math.min(200, Math.max(50, duration * 5));

  return (
    <div className="flex items-center gap-2 mb-2">
      <span className="text-xs w-20 text-slate-400">{startTime || '—'}</span>
      <div
        className="h-6 bg-emerald-600 rounded relative flex items-center justify-center text-xs text-white"
        style={{ width: `${width}px` }}
      >
        {label}
      </div>
      <span className="text-xs w-20 text-slate-400">{endTime || '—'}</span>
    </div>
  );
}
