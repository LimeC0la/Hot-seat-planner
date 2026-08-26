import copy
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import dateutil.parser

from .models import AppState, PlannedSegment, Operator, Machine, Assignment, Break, Settings


def get_shift_bounds(now: datetime):
    if 7 <= now.hour < 19:
        start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=19, minute=0, second=0, microsecond=0)
    elif now.hour >= 19:
        start = now.replace(hour=19, minute=0, second=0, microsecond=0)
        end = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    else:  # now.hour < 7
        start = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        end = now.replace(hour=7, minute=0, second=0, microsecond=0)
    return start, end


class SimOperator:
    def __init__(
        self,
        op: Operator,
        total_machine_seconds: float = 0.0,
        breaks_taken: int = 0,
        last_break_end: Optional[datetime] = None,
        available_at: datetime = None
    ):
        self.name = op.name
        self.qualifications = list(op.qualifications)
        self.status = op.status
        self.standby_time_minutes = op.standbyTimeMinutes
        self.breaks_taken = breaks_taken
        self.last_break_end = last_break_end
        self.total_machine_seconds = total_machine_seconds
        self.available_at = available_at or datetime.now()
        self.planned_breaks_count = 0

    def can_take_break(self, at_time: datetime, shift_start: datetime, shift_end: datetime, settings: Settings) -> bool:
        # Total breaks (historical + planned) must not exceed target
        if (self.breaks_taken + self.planned_breaks_count) >= settings.targetBreaksPerShift:
            return False

        # No breaks in first N minutes of shift
        break_window_start = shift_start + timedelta(minutes=settings.shiftBreakWindowStartOffsetMinutes)
        if at_time < break_window_start:
            return False

        # No breaks ending in last N minutes of shift
        break_dur = timedelta(minutes=settings.breakDurationMinutes)
        break_window_end = shift_end - timedelta(minutes=settings.shiftBreakWindowEndOffsetMinutes)
        if at_time + break_dur > break_window_end:
            return False

        # Minimum cooldown between consecutive breaks for same operator
        if self.last_break_end is not None:
            cooldown = timedelta(minutes=settings.breakCooldownMinutes)
            if at_time < self.last_break_end + cooldown:
                return False

        return True


class ReliefPlanner:
    """Break-first relief planner.

    Instead of swapping operators on a fixed rotation timer, this planner:
    1. Calculates total breaks the crew needs across the shift.
    2. Spaces break rounds evenly across the available break window.
    3. Only generates swaps where a break requires relief coverage.
    4. Keeps operators on their machines continuously between breaks.

    Two modes depending on crew/machine ratio:
    - SYNCHRONIZED (0 spare operators): everyone breaks at the same time,
      all machines park up together to synchronise production.
    - STAGGERED (has spare operators): machine operators take turns going
      on break, covered by spare operators from standby.
    """

    def __init__(self, state: AppState):
        self.state = state

    def generate_plan(self, now: Optional[datetime] = None) -> List[PlannedSegment]:
        if not self.state.settings.autoPlanEnabled:
            return []

        if now is None:
            now = datetime.now()

        shift_start, shift_end = get_shift_bounds(now)
        if now >= shift_end:
            return []

        settings = self.state.settings
        break_duration_seconds = max(5, settings.breakDurationMinutes) * 60
        break_dur = timedelta(seconds=break_duration_seconds)
        cooldown = timedelta(minutes=settings.breakCooldownMinutes)

        # ──────────────────────────────────────────────────────────────
        # 1. Gather historical machine operating time per operator
        # ──────────────────────────────────────────────────────────────
        machine_seconds_by_op: Dict[str, float] = {op.name: 0.0 for op in self.state.operators}
        for a in self.state.assignments:
            if a.operatorId in machine_seconds_by_op:
                try:
                    a_start = max(shift_start, dateutil.parser.isoparse(a.startTime))
                    a_end = min(now, dateutil.parser.isoparse(a.endTime)) if a.endTime else now
                    if a_end > a_start:
                        machine_seconds_by_op[a.operatorId] += (a_end - a_start).total_seconds()
                except Exception:
                    pass

        # ──────────────────────────────────────────────────────────────
        # 2. Gather historical breaks taken and last break end time
        # ──────────────────────────────────────────────────────────────
        breaks_by_op: Dict[str, int] = {op.name: 0 for op in self.state.operators}
        last_break_end_by_op: Dict[str, Optional[datetime]] = {op.name: None for op in self.state.operators}

        for b in self.state.breaks:
            if b.operatorId in breaks_by_op:
                try:
                    b_start = max(shift_start, dateutil.parser.isoparse(b.startTime))
                    max_b_end = b_start + break_dur
                    b_end = min(shift_end, dateutil.parser.isoparse(b.endTime), max_b_end) if b.endTime else min(shift_end, max_b_end)
                    if b_end > shift_start:
                        breaks_by_op[b.operatorId] += 1
                        prev_last = last_break_end_by_op[b.operatorId]
                        if prev_last is None or b_end > prev_last:
                            last_break_end_by_op[b.operatorId] = b_end
                except Exception:
                    pass

        # ──────────────────────────────────────────────────────────────
        # 3. Build simulation operator state
        # ──────────────────────────────────────────────────────────────
        sim_ops: Dict[str, SimOperator] = {}
        for op in self.state.operators:
            if op.status == 'absent':
                continue
            available_time = now
            last_b_end = last_break_end_by_op.get(op.name, None)
            if op.status == 'on_break':
                active_break = next(
                    (b for b in reversed(self.state.breaks)
                     if b.operatorId == op.name and not b.endTime),
                    None
                )
                if active_break:
                    try:
                        b_start = dateutil.parser.isoparse(active_break.startTime)
                        available_time = max(now, min(shift_end, b_start + break_dur))
                    except Exception:
                        available_time = now + break_dur
                else:
                    available_time = now + break_dur
                last_b_end = available_time

            sim_ops[op.name] = SimOperator(
                op=op,
                total_machine_seconds=machine_seconds_by_op.get(op.name, 0.0),
                breaks_taken=breaks_by_op.get(op.name, 0),
                last_break_end=last_b_end,
                available_at=available_time
            )

        if not sim_ops:
            return []

        planned_segments: List[PlannedSegment] = []

        # ──────────────────────────────────────────────────────────────
        # 4. Determine machine state and primary assignments
        # ──────────────────────────────────────────────────────────────
        operational_machines = [m for m in self.state.machines if m.status == 'operational']
        if not operational_machines:
            return []

        machine_type_map = {m.name: m.type for m in operational_machines}

        # Map: machine -> primary operator (the operator "assigned" for the shift)
        machine_op: Dict[str, str] = {}    # machine_name -> op_name
        op_machine: Dict[str, str] = {}    # op_name -> machine_name

        # First pass: operators currently working on machines
        for m in operational_machines:
            if m.currentOperatorId and m.currentOperatorId in sim_ops:
                machine_op[m.name] = m.currentOperatorId
                op_machine[m.currentOperatorId] = m.name

        # Second pass: recover primaries for operators currently on break
        # (their assignment was closed when they went on break, but they
        #  should return to the same machine)
        for m in operational_machines:
            if m.name not in machine_op:
                for a in reversed(self.state.assignments):
                    if a.machineId == m.name and a.endTime:
                        op_id = a.operatorId
                        if (op_id in sim_ops
                                and sim_ops[op_id].status == 'on_break'
                                and op_id not in op_machine):
                            machine_op[m.name] = op_id
                            op_machine[op_id] = m.name
                        break  # only check most recent assignment for this machine

        # Third pass: assign spare operators to still-unassigned machines
        unassigned_machines = [m for m in operational_machines if m.name not in machine_op]
        available_for_assign = [
            n for n in sim_ops
            if n not in op_machine and sim_ops[n].available_at <= now
        ]
        for m in unassigned_machines:
            for spare_name in list(available_for_assign):
                if m.type in sim_ops[spare_name].qualifications:
                    machine_op[m.name] = spare_name
                    op_machine[spare_name] = m.name
                    available_for_assign.remove(spare_name)
                    break

        # Spare operators = everyone not assigned to a machine
        spare_ops = [n for n in sim_ops if n not in op_machine]
        spare_count = len(spare_ops)

        # Sort spares by preference for relief selection
        if settings.preferEvenWorkTime:
            # Prefer spares with least machine time (give them seat time)
            spare_ops.sort(key=lambda n: sim_ops[n].total_machine_seconds)
        else:
            # Prefer spares who've been on standby longest
            spare_ops.sort(key=lambda n: -sim_ops[n].standby_time_minutes)

        # ──────────────────────────────────────────────────────────────
        # 5. Calculate break window and demand
        # ──────────────────────────────────────────────────────────────
        break_win_start = max(now, shift_start + timedelta(minutes=settings.shiftBreakWindowStartOffsetMinutes))
        break_win_end = shift_end - timedelta(minutes=settings.shiftBreakWindowEndOffsetMinutes)
        last_possible_start = break_win_end - break_dur  # latest a break can BEGIN

        # Per-operator scheduling state (mutable during planning)
        op_sched_breaks: Dict[str, int] = {n: sim_ops[n].breaks_taken for n in sim_ops}
        op_sched_last_end: Dict[str, Optional[datetime]] = {n: sim_ops[n].last_break_end for n in sim_ops}

        # Collected break events: (start, end, op_name, machine_name|None, relief_op|None)
        break_events: List[tuple] = []
        # Track when spares are busy covering machines
        spare_busy: List[tuple] = []  # (start, end, spare_name)

        has_valid_window = last_possible_start > break_win_start and settings.targetBreaksPerShift > 0

        if has_valid_window:
            if spare_count == 0:
                # ═════════════════════════════════════════════════════
                # MODE A — SYNCHRONIZED BREAKS (0 spare operators)
                # All operators break at the same time.
                # All machines park up together to synchronise production.
                # ═════════════════════════════════════════════════════
                max_remaining = max(
                    (settings.targetBreaksPerShift - op_sched_breaks.get(n, 0))
                    for n in sim_ops
                )
                num_rounds = max(0, max_remaining)

                if num_rounds > 0:
                    available_seconds = (last_possible_start - break_win_start).total_seconds()

                    # Evenly centre rounds within the window
                    if num_rounds == 1:
                        round_times = [break_win_start + timedelta(seconds=available_seconds / 2)]
                    else:
                        interval = available_seconds / (num_rounds + 1)
                        round_times = [
                            break_win_start + timedelta(seconds=(i + 1) * interval)
                            for i in range(num_rounds)
                        ]

                    for round_time in round_times:
                        for op_name in list(sim_ops.keys()):
                            remaining = settings.targetBreaksPerShift - op_sched_breaks.get(op_name, 0)
                            if remaining <= 0:
                                continue
                            # Cooldown check
                            last_end = op_sched_last_end.get(op_name)
                            if last_end and round_time < last_end + cooldown:
                                continue
                            # Window bounds check
                            if round_time + break_dur > break_win_end:
                                continue
                            # Availability check (operator might still be on a current break)
                            if sim_ops[op_name].available_at > round_time:
                                continue

                            machine_name = op_machine.get(op_name)  # None for standby ops
                            break_events.append((round_time, round_time + break_dur, op_name, machine_name, None))
                            op_sched_breaks[op_name] = op_sched_breaks.get(op_name, 0) + 1
                            op_sched_last_end[op_name] = round_time + break_dur

            else:
                # ═════════════════════════════════════════════════════
                # MODE B — STAGGERED BREAKS (has spare operators)
                # Machine operators take turns going on break.
                # Spare operators cover their machines during breaks.
                # ═════════════════════════════════════════════════════

                # --- Phase B1: Schedule machine-operator breaks ---
                machine_breaks_needed = sum(
                    max(0, settings.targetBreaksPerShift - op_sched_breaks.get(n, 0))
                    for n in op_machine
                )
                max_concurrent = spare_count

                if machine_breaks_needed > 0 and max_concurrent > 0:
                    num_rounds = math.ceil(machine_breaks_needed / max_concurrent)
                    available_seconds = (last_possible_start - break_win_start).total_seconds()

                    # Evenly centre rounds within the window
                    if num_rounds == 1:
                        round_times = [break_win_start + timedelta(seconds=available_seconds / 2)]
                    else:
                        interval = available_seconds / (num_rounds + 1)
                        round_times = [
                            break_win_start + timedelta(seconds=(i + 1) * interval)
                            for i in range(num_rounds)
                        ]

                    for round_time in round_times:
                        # Eligible machine operators for this round
                        eligible = []
                        for op_name in op_machine:
                            remaining = settings.targetBreaksPerShift - op_sched_breaks.get(op_name, 0)
                            if remaining <= 0:
                                continue
                            last_end = op_sched_last_end.get(op_name)
                            if last_end and round_time < last_end + cooldown:
                                continue
                            if round_time + break_dur > break_win_end:
                                continue
                            if sim_ops[op_name].available_at > round_time:
                                continue
                            eligible.append(op_name)

                        # Priority: operators who've gone longest since their last rest
                        def break_urgency(name):
                            last = op_sched_last_end.get(name) or shift_start
                            return (round_time - last).total_seconds()
                        eligible.sort(key=lambda n: -break_urgency(n))

                        slots_filled = 0
                        for op_name in eligible:
                            if slots_filled >= max_concurrent:
                                break

                            machine_name = op_machine[op_name]
                            machine_type = machine_type_map.get(machine_name, '')

                            # Find a qualified, available spare for relief
                            relief_op = self._find_relief(
                                machine_type, spare_ops, sim_ops, spare_busy,
                                round_time, break_dur
                            )
                            if relief_op is None:
                                continue  # no qualified spare available this round

                            bs, be = round_time, round_time + break_dur
                            break_events.append((bs, be, op_name, machine_name, relief_op))
                            spare_busy.append((bs, be, relief_op))
                            op_sched_breaks[op_name] = op_sched_breaks.get(op_name, 0) + 1
                            op_sched_last_end[op_name] = be
                            slots_filled += 1

                # --- Phase B2: Fallback for missed machine-op breaks ---
                for op_name in list(op_machine.keys()):
                    remaining = settings.targetBreaksPerShift - op_sched_breaks.get(op_name, 0)
                    while remaining > 0:
                        cursor = max(break_win_start, sim_ops[op_name].available_at)
                        last_end = op_sched_last_end.get(op_name)
                        if last_end:
                            cursor = max(cursor, last_end + cooldown)

                        found = False
                        while cursor + break_dur <= break_win_end:
                            machine_name = op_machine[op_name]
                            machine_type = machine_type_map.get(machine_name, '')
                            relief_op = self._find_relief(
                                machine_type, spare_ops, sim_ops, spare_busy,
                                cursor, break_dur
                            )
                            if relief_op is not None:
                                bs, be = cursor, cursor + break_dur
                                break_events.append((bs, be, op_name, machine_name, relief_op))
                                spare_busy.append((bs, be, relief_op))
                                op_sched_breaks[op_name] += 1
                                op_sched_last_end[op_name] = be
                                remaining -= 1
                                found = True
                                break
                            cursor += timedelta(minutes=15)
                        if not found:
                            break

                # --- Phase B3: Schedule standby (spare) operator breaks ---
                for spare_name in spare_ops:
                    remaining = settings.targetBreaksPerShift - op_sched_breaks.get(spare_name, 0)
                    while remaining > 0:
                        cursor = max(break_win_start, sim_ops[spare_name].available_at)
                        last_end = op_sched_last_end.get(spare_name)
                        if last_end:
                            cursor = max(cursor, last_end + cooldown)

                        found = False
                        while cursor + break_dur <= break_win_end:
                            # Spare must not be covering a machine at this time
                            busy = any(
                                s == spare_name
                                and not (cursor + break_dur <= ss or cursor >= se)
                                for ss, se, s in spare_busy
                            )
                            if not busy:
                                bs, be = cursor, cursor + break_dur
                                break_events.append((bs, be, spare_name, None, None))
                                op_sched_breaks[spare_name] += 1
                                op_sched_last_end[spare_name] = be
                                remaining -= 1
                                found = True
                                break
                            cursor += timedelta(minutes=15)
                        if not found:
                            break

        # ──────────────────────────────────────────────────────────────
        # 6. Generate PlannedSegments from break schedule
        # ──────────────────────────────────────────────────────────────
        break_events.sort(key=lambda x: x[0])

        # --- Machine assignment segments ---
        for m in operational_machines:
            primary_op = machine_op.get(m.name)
            if not primary_op:
                continue

            # All breaks affecting this machine, sorted chronologically
            m_breaks = sorted(
                [(bs, be, op, rel) for bs, be, op, mn, rel in break_events if mn == m.name],
                key=lambda x: x[0]
            )

            seg_start = now
            primary_available = sim_ops[primary_op].available_at

            # If primary is currently on break, a spare covers until they return
            if primary_available > now and sim_ops[primary_op].status == 'on_break':
                # Find any spare that can cover until primary returns
                cover_spare = None
                for sn in spare_ops:
                    if (m.type in sim_ops[sn].qualifications
                            and sim_ops[sn].available_at <= now
                            and sn not in op_machine):
                        cover_spare = sn
                        break
                if cover_spare:
                    planned_segments.append(PlannedSegment(
                        startTime=now.isoformat(),
                        endTime=primary_available.isoformat(),
                        operatorName=cover_spare,
                        machineName=m.name,
                        segmentType="assignment"
                    ))
                seg_start = primary_available

            for bs, be, _break_op, relief_op in m_breaks:
                if bs < seg_start:
                    continue  # break is before current segment start

                # Primary operator assignment segment before this break
                if bs > seg_start:
                    planned_segments.append(PlannedSegment(
                        startTime=seg_start.isoformat(),
                        endTime=bs.isoformat(),
                        operatorName=primary_op,
                        machineName=m.name,
                        segmentType="assignment"
                    ))

                # Relief operator covers machine during the break
                if relief_op:
                    planned_segments.append(PlannedSegment(
                        startTime=bs.isoformat(),
                        endTime=be.isoformat(),
                        operatorName=relief_op,
                        machineName=m.name,
                        segmentType="assignment"
                    ))
                # else: machine is idle (synchronized break — no segment)

                seg_start = be

            # Final assignment segment from last break to shift end
            if seg_start < shift_end:
                planned_segments.append(PlannedSegment(
                    startTime=seg_start.isoformat(),
                    endTime=shift_end.isoformat(),
                    operatorName=primary_op,
                    machineName=m.name,
                    segmentType="assignment"
                ))

        # --- Break segments for all operators ---
        for bs, be, op_name, _mn, _rel in break_events:
            planned_segments.append(PlannedSegment(
                startTime=bs.isoformat(),
                endTime=be.isoformat(),
                operatorName=op_name,
                machineName="",
                segmentType="break"
            ))

        planned_segments.sort(key=lambda s: s.startTime)
        return planned_segments

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _find_relief(
        machine_type: str,
        spare_ops: List[str],
        sim_ops: Dict[str, SimOperator],
        spare_busy: List[tuple],
        at_time: datetime,
        break_dur: timedelta
    ) -> Optional[str]:
        """Find a qualified spare operator available to cover a machine
        of *machine_type* during [at_time, at_time + break_dur]."""
        for spare_name in spare_ops:
            if machine_type not in sim_ops[spare_name].qualifications:
                continue
            # Must be available (not still on their own break)
            if sim_ops[spare_name].available_at > at_time:
                continue
            # Must not already be covering another machine at this time
            busy = any(
                s == spare_name
                and not (at_time + break_dur <= ss or at_time >= se)
                for ss, se, s in spare_busy
            )
            if busy:
                continue
            return spare_name
        return None
