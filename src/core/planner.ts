import type { AppState, PlannedSegment, Machine, Circuit } from './types.ts';

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

export function getMachineOperationalShell(
  machine: Machine,
  circuits: Circuit[]
): 'circuit_leader' | 'circuit_truck' | 'bench_support' | 'pit_service' {
  if (machine.operationalShell) return machine.operationalShell;

  if (circuits.some(c => c.diggerId === machine.name || c.id === machine.name)) {
    return 'circuit_leader';
  }
  if (circuits.some(c => c.truckIds.includes(machine.name))) {
    return 'circuit_truck';
  }
  if (machine.type.toLowerCase().includes('dozer')) {
    return 'bench_support';
  }
  if (machine.type.toLowerCase().includes('grader') || machine.type.toLowerCase().includes('water')) {
    return 'pit_service';
  }
  if (
    machine.type.toLowerCase().includes('loader') ||
    machine.type.toLowerCase().includes('excavator') ||
    machine.type.toLowerCase().includes('digger')
  ) {
    return 'circuit_leader';
  }
  return 'pit_service';
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

interface BreakEvent {
  start: Date;
  end: Date;
  operatorName: string;
  machineName: string;
  reliefName?: string;
  isCircuitCrib?: boolean;
  isHotseatRelief?: boolean;
  isLocked?: boolean;
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

    // 1. Gather historical break stats
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

    // Break Window Boundaries
    const breakWindowStart = new Date(shiftStart.getTime() + settings.shiftBreakWindowStartOffsetMinutes * 60 * 1000);
    const breakWindowEnd = new Date(shiftEnd.getTime() - settings.shiftBreakWindowEndOffsetMinutes * 60 * 1000);
    const effectiveWindowStart = new Date(Math.max(now.getTime(), breakWindowStart.getTime()));

    const breakEvents: BreakEvent[] = [];
    const spareBusy: { start: Date; end: Date; spareName: string }[] = [];

    // ─────────────────────────────────────────────────────────────
    // STEP 1: APPLY MANUAL RELIEF LOCKS (Supervisor Overrides)
    // ─────────────────────────────────────────────────────────────
    if (this.state.manualReliefs && this.state.manualReliefs.length > 0) {
      for (const lock of this.state.manualReliefs) {
        if (!lock.locked) continue;
        const targetMach = operationalMachines.find(m => m.name === lock.machineName);
        if (!targetMach || !targetMach.currentOperatorId) continue;

        try {
          const lStart = new Date(lock.startTime);
          const lEnd = new Date(lock.endTime);
          if (lEnd <= now) continue;

          breakEvents.push({
            start: lStart,
            end: lEnd,
            operatorName: targetMach.currentOperatorId,
            machineName: targetMach.name,
            reliefName: lock.reliefOperatorName,
            isHotseatRelief: true,
            isLocked: true
          });

          spareBusy.push({
            start: lStart,
            end: lEnd,
            spareName: lock.reliefOperatorName
          });

          if (simOps[targetMach.currentOperatorId]) {
            simOps[targetMach.currentOperatorId].plannedBreaksCount++;
            simOps[targetMach.currentOperatorId].lastBreakEnd = lEnd;
          }
        } catch {
          // ignore parse errors
        }
      }
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 2: SHELL 1 — DIRECT PRODUCTION CIRCUITS (Digger + Trucks)
    // ─────────────────────────────────────────────────────────────
    const circuitsByZone: Record<string, Circuit[]> = {};
    for (const c of this.state.circuits) {
      const z = c.zoneId || 'General';
      if (!circuitsByZone[z]) circuitsByZone[z] = [];
      circuitsByZone[z].push(c);
    }

    const midWindowMs = effectiveWindowStart.getTime() + (breakWindowEnd.getTime() - effectiveWindowStart.getTime()) * 0.45;

    for (const [zoneId, zoneCircuits] of Object.entries(circuitsByZone)) {
      const areaConfig = this.state.areaShutdownConfigs?.[zoneId] || {
        zoneId,
        mode: 'staggered',
        staggerMinutes: 30
      };

      zoneCircuits.forEach((circuit, circuitIdx) => {
        const digger = operationalMachines.find(
          m => m.name === circuit.diggerId || m.name === circuit.id
        );
        if (!digger || !digger.currentOperatorId) return;

        const diggerOp = digger.currentOperatorId;
        const sim = simOps[diggerOp];
        if (!sim) return;

        const existingLock = breakEvents.find(e => e.machineName === digger.name);
        if (existingLock) return;

        const neededBreaks = Math.max(0, settings.targetBreaksPerShift - (sim.breaksTaken + sim.plannedBreaksCount));
        if (neededBreaks <= 0) return;

        const shutdownMode = circuit.shutdownMode || areaConfig.mode || 'staggered';
        const staggerMinutes = circuit.staggerOffsetMinutes ?? areaConfig.staggerMinutes ?? 30;

        let candidateStart = new Date(midWindowMs);
        if (shutdownMode === 'staggered') {
          candidateStart = new Date(midWindowMs + circuitIdx * staggerMinutes * 60 * 1000);
        }

        if (sim.lastBreakEnd) {
          const minAllowed = new Date(sim.lastBreakEnd.getTime() + cooldownMs);
          if (candidateStart < minAllowed) candidateStart = minAllowed;
        }

        const candidateEnd = new Date(candidateStart.getTime() + breakDurationMs);
        if (candidateEnd > breakWindowEnd) return;

        const reliefSpare = this.findReliefSpare(
          digger.type,
          spareOpNames,
          simOps,
          spareBusy,
          candidateStart,
          candidateEnd
        );

        const assignedTrucks = operationalMachines.filter(
          m => circuit.truckIds.includes(m.name) && m.currentOperatorId
        );

        if (reliefSpare) {
          // ── Digger IS HOT-SEATED: Continuous Production ──
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = candidateEnd;

          breakEvents.push({
            start: candidateStart,
            end: candidateEnd,
            operatorName: diggerOp,
            machineName: digger.name,
            reliefName: reliefSpare,
            isHotseatRelief: true
          });

          spareBusy.push({
            start: candidateStart,
            end: candidateEnd,
            spareName: reliefSpare
          });

          let truckStaggerIdx = 0;
          for (const trk of assignedTrucks) {
            const trkOp = trk.currentOperatorId!;
            const trkSim = simOps[trkOp];
            if (!trkSim) continue;
            if (trkSim.breaksTaken + trkSim.plannedBreaksCount >= settings.targetBreaksPerShift) continue;

            const trkStart = new Date(candidateStart.getTime() + truckStaggerIdx * 15 * 60 * 1000);
            const trkEnd = new Date(trkStart.getTime() + breakDurationMs);
            if (trkEnd > breakWindowEnd) continue;

            const trkRelief = this.findReliefSpare(
              trk.type,
              spareOpNames,
              simOps,
              spareBusy,
              trkStart,
              trkEnd
            );

            if (trkRelief) {
              trkSim.plannedBreaksCount++;
              trkSim.lastBreakEnd = trkEnd;
              breakEvents.push({
                start: trkStart,
                end: trkEnd,
                operatorName: trkOp,
                machineName: trk.name,
                reliefName: trkRelief,
                isHotseatRelief: true
              });
              spareBusy.push({ start: trkStart, end: trkEnd, spareName: trkRelief });
              truckStaggerIdx++;
            }
          }
        } else {
          // ── Digger CANNOT be hot-seated: CIRCUIT SYNCHRONIZED CRIB ──
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = candidateEnd;

          breakEvents.push({
            start: candidateStart,
            end: candidateEnd,
            operatorName: diggerOp,
            machineName: digger.name,
            isCircuitCrib: true
          });

          for (const trk of assignedTrucks) {
            const trkOp = trk.currentOperatorId!;
            const trkSim = simOps[trkOp];
            if (trkSim) {
              trkSim.plannedBreaksCount++;
              trkSim.lastBreakEnd = candidateEnd;
            }

            breakEvents.push({
              start: candidateStart,
              end: candidateEnd,
              operatorName: trkOp,
              machineName: trk.name,
              isCircuitCrib: true
            });
          }
        }
      });
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 3: SHELL 2 — BENCH & DUMP SUPPORT DOZERS
    // ─────────────────────────────────────────────────────────────
    const operationalDozers = operationalMachines.filter(m => m.type.toLowerCase().includes('dozer'));

    for (const dozer of operationalDozers) {
      if (!dozer.currentOperatorId) continue;
      if (breakEvents.some(e => e.machineName === dozer.name)) continue;

      const op = dozer.currentOperatorId;
      const sim = simOps[op];
      if (!sim) continue;
      if (sim.breaksTaken + sim.plannedBreaksCount >= settings.targetBreaksPerShift) continue;

      const role = dozer.dozerRole || (dozer.zoneId === 'ROM Pad' ? 'dump' : 'pit');

      if (role === 'pit') {
        const localDigger = operationalMachines.find(
          m => m.zoneId === dozer.zoneId && (m.type.toLowerCase().includes('digger') || m.type.toLowerCase().includes('excavator'))
        );
        const diggerCrib = localDigger
          ? breakEvents.find(e => e.machineName === localDigger.name)
          : null;

        if (diggerCrib) {
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = diggerCrib.end;
          breakEvents.push({
            start: diggerCrib.start,
            end: diggerCrib.end,
            operatorName: op,
            machineName: dozer.name,
            isCircuitCrib: diggerCrib.isCircuitCrib
          });
        } else {
          const bStart = new Date(midWindowMs);
          const bEnd = new Date(bStart.getTime() + breakDurationMs);
          const relief = this.findReliefSpare(dozer.type, spareOpNames, simOps, spareBusy, bStart, bEnd);
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = bEnd;
          breakEvents.push({
            start: bStart,
            end: bEnd,
            operatorName: op,
            machineName: dozer.name,
            reliefName: relief || undefined,
            isHotseatRelief: Boolean(relief)
          });
          if (relief) spareBusy.push({ start: bStart, end: bEnd, spareName: relief });
        }
      } else {
        const bStart = new Date(midWindowMs + 45 * 60 * 1000);
        const bEnd = new Date(bStart.getTime() + breakDurationMs);

        const relief = this.findReliefSpare(dozer.type, spareOpNames, simOps, spareBusy, bStart, bEnd);
        if (relief) {
          sim.plannedBreaksCount++;
          sim.lastBreakEnd = bEnd;
          breakEvents.push({
            start: bStart,
            end: bEnd,
            operatorName: op,
            machineName: dozer.name,
            reliefName: relief,
            isHotseatRelief: true
          });
          spareBusy.push({ start: bStart, end: bEnd, spareName: relief });
        } else {
          const sharedCrib = breakEvents.find(e => e.isCircuitCrib);
          const targetStart = sharedCrib ? sharedCrib.start : bStart;
          const targetEnd = sharedCrib ? sharedCrib.end : bEnd;

          sim.plannedBreaksCount++;
          sim.lastBreakEnd = targetEnd;
          breakEvents.push({
            start: targetStart,
            end: targetEnd,
            operatorName: op,
            machineName: dozer.name,
            isCircuitCrib: Boolean(sharedCrib)
          });
        }
      }
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 4: SHELL 3 — PIT SERVICES (Water Carts & Graders)
    // ─────────────────────────────────────────────────────────────
    const waterCarts = operationalMachines.filter(m => m.type.toLowerCase().includes('water'));
    const graders = operationalMachines.filter(m => m.type.toLowerCase().includes('grader'));

    waterCarts.forEach((wc, idx) => {
      if (!wc.currentOperatorId) return;
      if (breakEvents.some(e => e.machineName === wc.name)) return;

      const op = wc.currentOperatorId;
      const sim = simOps[op];
      if (!sim) return;
      if (sim.breaksTaken + sim.plannedBreaksCount >= settings.targetBreaksPerShift) return;

      const wcStart = new Date(effectiveWindowStart.getTime() + (idx * 45 + 30) * 60 * 1000);
      const wcEnd = new Date(wcStart.getTime() + breakDurationMs);
      if (wcEnd > breakWindowEnd) return;

      const relief = this.findReliefSpare(wc.type, spareOpNames, simOps, spareBusy, wcStart, wcEnd);
      sim.plannedBreaksCount++;
      sim.lastBreakEnd = wcEnd;

      breakEvents.push({
        start: wcStart,
        end: wcEnd,
        operatorName: op,
        machineName: wc.name,
        reliefName: relief || undefined,
        isHotseatRelief: Boolean(relief)
      });
      if (relief) spareBusy.push({ start: wcStart, end: wcEnd, spareName: relief });
    });

    graders.forEach((gr, idx) => {
      if (!gr.currentOperatorId) return;
      if (breakEvents.some(e => e.machineName === gr.name)) return;

      const op = gr.currentOperatorId;
      const sim = simOps[op];
      if (!sim) return;
      if (sim.breaksTaken + sim.plannedBreaksCount >= settings.targetBreaksPerShift) return;

      const grStart = new Date(effectiveWindowStart.getTime() + (idx * 60 + 15) * 60 * 1000);
      const grEnd = new Date(grStart.getTime() + breakDurationMs);
      if (grEnd > breakWindowEnd) return;

      const relief = this.findReliefSpare(gr.type, spareOpNames, simOps, spareBusy, grStart, grEnd);
      sim.plannedBreaksCount++;
      sim.lastBreakEnd = grEnd;

      breakEvents.push({
        start: grStart,
        end: grEnd,
        operatorName: op,
        machineName: gr.name,
        reliefName: relief || undefined,
        isHotseatRelief: Boolean(relief)
      });
      if (relief) spareBusy.push({ start: grStart, end: grEnd, spareName: relief });
    });

    // ─────────────────────────────────────────────────────────────
    // STEP 5: ANY REMAINING UNPLANNED OPERATIONAL MACHINES
    // ─────────────────────────────────────────────────────────────
    for (const m of operationalMachines) {
      if (!m.currentOperatorId) continue;

      const op = m.currentOperatorId;
      const sim = simOps[op];
      if (!sim) continue;
      const neededBreaks = Math.max(0, settings.targetBreaksPerShift - (sim.breaksTaken + sim.plannedBreaksCount));
      if (neededBreaks <= 0) continue;

      const remainingTimeMs = breakWindowEnd.getTime() - effectiveWindowStart.getTime();
      const stepMs = remainingTimeMs / (neededBreaks + 1);

      for (let i = 1; i <= neededBreaks; i++) {
        const bStart = new Date(effectiveWindowStart.getTime() + i * stepMs);
        const bEnd = new Date(bStart.getTime() + breakDurationMs);
        const relief = this.findReliefSpare(m.type, spareOpNames, simOps, spareBusy, bStart, bEnd);

        sim.plannedBreaksCount++;
        sim.lastBreakEnd = bEnd;

        breakEvents.push({
          start: bStart,
          end: bEnd,
          operatorName: op,
          machineName: m.name,
          reliefName: relief || undefined,
          isHotseatRelief: Boolean(relief)
        });
        if (relief) spareBusy.push({ start: bStart, end: bEnd, spareName: relief });
      }
    }

    // ─────────────────────────────────────────────────────────────
    // STEP 6: CONSTRUCT TIMELINE SEGMENTS
    // ─────────────────────────────────────────────────────────────
    const plannedSegments: PlannedSegment[] = [];

    for (const m of operationalMachines) {
      if (!m.currentOperatorId) continue;
      const primaryOp = m.currentOperatorId;

      const machEvents = breakEvents
        .filter(ev => ev.machineName === m.name)
        .sort((a, b) => a.start.getTime() - b.start.getTime());

      let cur = now;
      for (const ev of machEvents) {
        if (ev.start > cur) {
          plannedSegments.push({
            startTime: cur.toISOString(),
            endTime: ev.start.toISOString(),
            operatorName: primaryOp,
            machineName: m.name,
            segmentType: 'assignment'
          });
        }

        if (ev.reliefName) {
          plannedSegments.push({
            startTime: ev.start.toISOString(),
            endTime: ev.end.toISOString(),
            operatorName: ev.reliefName,
            machineName: m.name,
            segmentType: 'assignment',
            isHotseatRelief: true
          });
        } else if (ev.isCircuitCrib) {
          plannedSegments.push({
            startTime: ev.start.toISOString(),
            endTime: ev.end.toISOString(),
            operatorName: primaryOp,
            machineName: m.name,
            segmentType: 'break',
            breakType: 'standard',
            isCircuitCrib: true
          });
        }

        cur = ev.end;
      }

      if (cur < shiftEnd) {
        plannedSegments.push({
          startTime: cur.toISOString(),
          endTime: shiftEnd.toISOString(),
          operatorName: primaryOp,
          machineName: m.name,
          segmentType: 'assignment'
        });
      }
    }

    for (const ev of breakEvents) {
      if (ev.end <= now) continue;
      plannedSegments.push({
        startTime: Math.max(now.getTime(), ev.start.getTime()) === now.getTime() ? now.toISOString() : ev.start.toISOString(),
        endTime: ev.end.toISOString(),
        operatorName: ev.operatorName,
        machineName: '',
        segmentType: 'break',
        breakType: 'standard',
        isCircuitCrib: ev.isCircuitCrib,
        isHotseatRelief: ev.isHotseatRelief
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

      if (!op.qualifications.includes(machineType) && machineType.toLowerCase() !== 'other') {
        continue;
      }

      if (op.availableAt > atStart) {
        continue;
      }

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
