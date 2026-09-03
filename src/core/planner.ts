import type { AppState, PlannedSegment } from './types.ts';

export interface ShiftBounds {
  shiftStart: Date;
  shiftEnd: Date;
  isDayShift: boolean;
  shiftName: string;
}

export function getShiftBounds(now: Date = new Date()): ShiftBounds {
  const year = now.getFullYear();
  const month = now.getMonth();
  const date = now.getDate();
  const hour = now.getHours();

  let shiftStart: Date;
  let shiftEnd: Date;
  let isDayShift = false;

  if (hour >= 7 && hour < 19) {
    // Day Shift: 07:00 -> 19:00 today
    shiftStart = new Date(year, month, date, 7, 0, 0, 0);
    shiftEnd = new Date(year, month, date, 19, 0, 0, 0);
    isDayShift = true;
  } else if (hour >= 19) {
    // Night Shift (started today 19:00 -> ends tomorrow 07:00)
    shiftStart = new Date(year, month, date, 19, 0, 0, 0);
    shiftEnd = new Date(year, month, date + 1, 7, 0, 0, 0);
    isDayShift = false;
  } else {
    // Night Shift (started yesterday 19:00 -> ends today 07:00)
    shiftStart = new Date(year, month, date - 1, 19, 0, 0, 0);
    shiftEnd = new Date(year, month, date, 7, 0, 0, 0);
    isDayShift = false;
  }

  return {
    shiftStart,
    shiftEnd,
    isDayShift,
    shiftName: isDayShift ? 'Day Shift (07:00 - 19:00)' : 'Night Shift (19:00 - 07:00)'
  };
}

export function formatShortName(fullName: string): string {
  if (!fullName) return '';
  const parts = fullName.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0]} ${parts[parts.length - 1][0]}.`;
  }
  return fullName;
}

export function formatDuration(totalSeconds: number): string {
  const totalMins = Math.round(totalSeconds / 60);
  const hours = Math.floor(totalMins / 60);
  const mins = totalMins % 60;
  if (hours > 0) {
    return `${hours}h ${mins.toString().padStart(2, '0')}m`;
  }
  return `${mins}m`;
}

interface SimOp {
  name: string;
  qualifications: string[];
  status: string;
  breaksTaken: number;
  plannedBreaksCount: number;
  lastBreakEnd: Date | null;
  availableAt: Date;
  totalMachineSeconds: number;
  currentZone: string;
}

export class ReliefPlanner {
  private state: AppState;

  constructor(state: AppState) {
    this.state = state;
  }

  public generatePlan(now: Date = new Date()): PlannedSegment[] {
    const settings = this.state.settings;
    if (!settings.autoPlanEnabled) {
      return [];
    }

    const { shiftStart, shiftEnd } = getShiftBounds(now);
    if (now >= shiftEnd) {
      return [];
    }

    const breakDurationMs = Math.max(5, settings.breakDurationMinutes) * 60 * 1000;
    const cooldownMs = settings.breakCooldownMinutes * 60 * 1000;

    // 1. Gather historical stats from assignments and breaks
    const breaksByOp: Record<string, number> = {};
    const lastBreakEndByOp: Record<string, Date | null> = {};
    const machineSecondsByOp: Record<string, number> = {};

    for (const op of this.state.operators) {
      breaksByOp[op.name] = 0;
      lastBreakEndByOp[op.name] = null;
      machineSecondsByOp[op.name] = 0;
    }

    for (const b of this.state.breaks) {
      if (b.operatorId in breaksByOp) {
        try {
          const bStart = new Date(b.startTime);
          const bEnd = b.endTime ? new Date(b.endTime) : now;
          if (bStart >= shiftStart && bStart < shiftEnd) {
            breaksByOp[b.operatorId]++;
            if (!lastBreakEndByOp[b.operatorId] || bEnd > lastBreakEndByOp[b.operatorId]!) {
              lastBreakEndByOp[b.operatorId] = bEnd;
            }
          }
        } catch {
          // ignore date parse errors
        }
      }
    }

    for (const a of this.state.assignments) {
      if (a.operatorId in machineSecondsByOp) {
        try {
          const aStart = Math.max(shiftStart.getTime(), new Date(a.startTime).getTime());
          const aEnd = a.endTime ? Math.min(now.getTime(), new Date(a.endTime).getTime()) : now.getTime();
          if (aEnd > aStart) {
            machineSecondsByOp[a.operatorId] += (aEnd - aStart) / 1000;
          }
        } catch {
          // ignore
        }
      }
    }

    // 2. Identify active operators and operational machines
    const operationalMachines = this.state.machines.filter(m => m.status === 'operational');
    const activeOperators = this.state.operators.filter(op => op.status !== 'absent');

    const simOps: Record<string, SimOp> = {};
    for (const op of activeOperators) {
      simOps[op.name] = {
        name: op.name,
        qualifications: [...op.qualifications],
        status: op.status,
        breaksTaken: breaksByOp[op.name] ?? 0,
        plannedBreaksCount: 0,
        lastBreakEnd: lastBreakEndByOp[op.name] ?? null,
        availableAt: now,
        totalMachineSeconds: machineSecondsByOp[op.name] ?? 0,
        currentZone: ''
      };
    }

    const assignedOpNames = new Set(
      operationalMachines.map(m => m.currentOperatorId).filter(Boolean) as string[]
    );

    const spareOpNames = activeOperators
      .filter(op => !assignedOpNames.has(op.name))
      .map(op => op.name);

    const plannedSegments: PlannedSegment[] = [];

    // Break Window Boundaries
    const breakWindowStart = new Date(shiftStart.getTime() + settings.shiftBreakWindowStartOffsetMinutes * 60 * 1000);
    const breakWindowEnd = new Date(shiftEnd.getTime() - settings.shiftBreakWindowEndOffsetMinutes * 60 * 1000);

    const effectiveWindowStart = new Date(Math.max(now.getTime(), breakWindowStart.getTime()));

    // ─────────────────────────────────────────────────────────────
    // MODE 1: SYNCHRONIZED BREAKS (0 spare operators)
    // ─────────────────────────────────────────────────────────────
    if (spareOpNames.length === 0) {
      const remainingWindowMs = breakWindowEnd.getTime() - effectiveWindowStart.getTime();
      const numRounds = Math.max(1, settings.targetBreaksPerShift);

      if (remainingWindowMs > numRounds * breakDurationMs) {
        const intervalMs = remainingWindowMs / (numRounds + 1);

        for (let r = 1; r <= numRounds; r++) {
          const bStart = new Date(effectiveWindowStart.getTime() + r * intervalMs);
          const bEnd = new Date(bStart.getTime() + breakDurationMs);

          if (bStart < now) continue;

          // All operators break together
          for (const op of activeOperators) {
            plannedSegments.push({
              startTime: bStart.toISOString(),
              endTime: bEnd.toISOString(),
              operatorName: op.name,
              machineName: '',
              segmentType: 'break',
              breakType: 'standard'
            });
          }
        }
      }

      // Operators stay on machines between breaks
      for (const m of operationalMachines) {
        if (!m.currentOperatorId) continue;
        const opName = m.currentOperatorId;

        const opBreaks = plannedSegments
          .filter(s => s.operatorName === opName && s.segmentType === 'break')
          .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());

        let cur = now;
        for (const b of opBreaks) {
          const bStart = new Date(b.startTime);
          const bEnd = new Date(b.endTime);

          if (bStart > cur) {
            plannedSegments.push({
              startTime: cur.toISOString(),
              endTime: bStart.toISOString(),
              operatorName: opName,
              machineName: m.name,
              segmentType: 'assignment'
            });
          }
          cur = bEnd;
        }

        if (cur < shiftEnd) {
          plannedSegments.push({
            startTime: cur.toISOString(),
            endTime: shiftEnd.toISOString(),
            operatorName: opName,
            machineName: m.name,
            segmentType: 'assignment'
          });
        }
      }

      return plannedSegments.sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
    }

    // ─────────────────────────────────────────────────────────────
    // MODE 2: STAGGERED BREAKS (with spare relief operators)
    // ─────────────────────────────────────────────────────────────
    interface BreakEvent {
      start: Date;
      end: Date;
      operatorName: string;
      machineName: string;
      reliefName: string;
    }

    const breakEvents: BreakEvent[] = [];
    const spareBusy: { start: Date; end: Date; spareName: string }[] = [];

    // Prioritize machines: Diggers (priority 1) first, then others
    const sortedMachines = [...operationalMachines].sort((a, b) => a.priority - b.priority);

    for (const m of sortedMachines) {
      if (!m.currentOperatorId) continue;
      const primaryOp = m.currentOperatorId;
      const sim = simOps[primaryOp];
      if (!sim) continue;

      const neededBreaks = Math.max(0, settings.targetBreaksPerShift - (sim.breaksTaken + sim.plannedBreaksCount));
      if (neededBreaks <= 0) continue;

      const remainingTimeMs = breakWindowEnd.getTime() - effectiveWindowStart.getTime();
      const stepMs = remainingTimeMs / (neededBreaks + 1);

      for (let i = 1; i <= neededBreaks; i++) {
        let candidateStart = new Date(effectiveWindowStart.getTime() + i * stepMs);

        // Enforce cooldown from last break
        if (sim.lastBreakEnd) {
          const minAllowed = new Date(sim.lastBreakEnd.getTime() + cooldownMs);
          if (candidateStart < minAllowed) {
            candidateStart = minAllowed;
          }
        }

        const candidateEnd = new Date(candidateStart.getTime() + breakDurationMs);
        if (candidateEnd > breakWindowEnd) continue;

        // Find available qualified relief spare
        const reliefSpare = this.findReliefSpare(
          m.type,
          spareOpNames,
          simOps,
          spareBusy,
          candidateStart,
          candidateEnd
        );

        if (reliefSpare) {
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = candidateEnd;

          breakEvents.push({
            start: candidateStart,
            end: candidateEnd,
            operatorName: primaryOp,
            machineName: m.name,
            reliefName: reliefSpare
          });

          spareBusy.push({
            start: candidateStart,
            end: candidateEnd,
            spareName: reliefSpare
          });
        }
      }
    }

    // Construct continuous timeline segments for each machine
    for (const m of operationalMachines) {
      if (!m.currentOperatorId) continue;
      const primaryOp = m.currentOperatorId;

      const machEvents = breakEvents
        .filter(ev => ev.machineName === m.name)
        .sort((a, b) => a.start.getTime() - b.start.getTime());

      let cur = now;
      for (const ev of machEvents) {
        if (ev.start > cur) {
          // Primary operator on machine
          plannedSegments.push({
            startTime: cur.toISOString(),
            endTime: ev.start.toISOString(),
            operatorName: primaryOp,
            machineName: m.name,
            segmentType: 'assignment'
          });
        }

        // Relief operator covers machine
        plannedSegments.push({
          startTime: ev.start.toISOString(),
          endTime: ev.end.toISOString(),
          operatorName: ev.reliefName,
          machineName: m.name,
          segmentType: 'assignment'
        });

        cur = ev.end;
      }

      if (cur < shiftEnd) {
        // Primary returns and finishes shift
        plannedSegments.push({
          startTime: cur.toISOString(),
          endTime: shiftEnd.toISOString(),
          operatorName: primaryOp,
          machineName: m.name,
          segmentType: 'assignment'
        });
      }
    }

    // Add Break segments for operators
    for (const ev of breakEvents) {
      if (ev.end <= now) continue;
      plannedSegments.push({
        startTime: Math.max(now.getTime(), ev.start.getTime()) === now.getTime() ? now.toISOString() : ev.start.toISOString(),
        endTime: ev.end.toISOString(),
        operatorName: ev.operatorName,
        machineName: '',
        segmentType: 'break',
        breakType: 'standard'
      });
    }

    return plannedSegments.sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
  }

  private findReliefSpare(
    machineType: string,
    spareNames: string[],
    simOps: Record<string, SimOp>,
    spareBusy: { start: Date; end: Date; spareName: string }[],
    atStart: Date,
    atEnd: Date
  ): string | null {
    for (const spareName of spareNames) {
      const op = simOps[spareName];
      if (!op) continue;

      // Must be qualified for this machine type
      if (!op.qualifications.includes(machineType) && machineType.toLowerCase() !== 'other') {
        continue;
      }

      // Must be available
      if (op.availableAt > atStart) {
        continue;
      }

      // Must not already be covering another machine
      const isBusy = spareBusy.some(
        b => b.spareName === spareName && !(atEnd.getTime() <= b.start.getTime() || atStart.getTime() >= b.end.getTime())
      );

      if (!isBusy) {
        return spareName;
      }
    }

    return null;
  }
}
