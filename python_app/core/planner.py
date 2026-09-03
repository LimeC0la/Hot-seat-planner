import copy
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import dateutil.parser

from .models import AppState, PlannedSegment, Operator, Machine, Assignment, Break, Settings, Zone, ZoneConnection


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
        available_at: datetime = None,
        current_zone: str = ""
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
        self.current_zone = current_zone

    def can_take_break(self, at_time: datetime, shift_start: datetime, shift_end: datetime, settings: Settings) -> bool:
        # Total breaks (historical + planned) must not exceed target
        if (self.breaks_taken + self.planned_breaks_count) >= settings.targetBreaksPerShift:
            # Unless workstretch is exceeded — then we MUST break (safety override)
            if not self.must_take_break(at_time, shift_start, settings):
                return False

        # No breaks in first N minutes of shift
        break_window_start = shift_start + timedelta(minutes=settings.shiftBreakWindowStartOffsetMinutes)
        if at_time < break_window_start:
            # Workstretch override: even outside the window, if dangerously fatigued
            if not self.must_take_break(at_time, shift_start, settings):
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
                # Workstretch override: skip cooldown if critically overworked
                if not self.must_take_break(at_time, shift_start, settings):
                    return False

        return True

    def must_take_break(self, at_time: datetime, shift_start: datetime, settings: Settings) -> bool:
        """Check if operator MUST take a break due to workstretch exceeding max.
        This is a safety hard constraint that overrides all other scheduling rules."""
        last_rest = self.last_break_end or shift_start
        work_since_rest = (at_time - last_rest).total_seconds() / 60.0
        return work_since_rest >= settings.maxWorkstretchMinutes


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
        # Zone data for travel time computation
        self.zones: List[Zone] = list(state.zones) if state.zones else []
        self.zone_connections: List[ZoneConnection] = list(state.zoneConnections) if state.zoneConnections else []
        self.machine_zone_map: Dict[str, str] = {
            m.name: m.zoneId for m in state.machines if m.zoneId
        }

    def _get_travel_time(self, from_zone: str, to_zone: str) -> int:
        """Return travel time in minutes between two zones using Dijkstra.

        Falls back to Euclidean distance between zone coordinates when
        no explicit ZoneConnection exists.  Returns 0 when zones are the
        same, unknown, or no zone data is configured.
        """
        if not from_zone or not to_zone or from_zone == to_zone:
            return 0

        import heapq

        zone_map = {z.id: z for z in self.zones}
        if from_zone not in zone_map or to_zone not in zone_map:
            return 0  # unknown zone — no penalty

        PIXELS_PER_MINUTE = 10.0
        graph: Dict[str, Dict[str, int]] = {z.id: {} for z in self.zones}

        # Build adjacency list with Euclidean defaults
        for z1 in self.zones:
            for z2 in self.zones:
                if z1.id != z2.id:
                    dist = math.hypot(z2.x - z1.x, z2.y - z1.y)
                    time = int(dist / PIXELS_PER_MINUTE)
                    graph[z1.id][z2.id] = time

        # Override with explicit connections
        for conn in self.zone_connections:
            if conn.zone_a in graph and conn.zone_b in graph:
                graph[conn.zone_a][conn.zone_b] = conn.travelTimeMinutes
                graph[conn.zone_b][conn.zone_a] = conn.travelTimeMinutes

        distances: Dict[str, float] = {node: float('infinity') for node in graph}
        distances[from_zone] = 0
        pq = [(0, from_zone)]

        while pq:
            current_dist, current_node = heapq.heappop(pq)

            if current_node == to_zone:
                return int(current_dist)

            if current_dist > distances[current_node]:
                continue

            for neighbor, weight in graph[current_node].items():
                distance = current_dist + weight
                if distance < distances.get(neighbor, float('infinity')):
                    distances[neighbor] = distance
                    heapq.heappush(pq, (distance, neighbor))

        return 0  # unreachable

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

            # Determine initial zone: look up the most recent machine assignment
            initial_zone = ""
            for a in reversed(self.state.assignments):
                if a.operatorId == op.name and a.machineId in self.machine_zone_map:
                    initial_zone = self.machine_zone_map[a.machineId]
                    break

            sim_ops[op.name] = SimOperator(
                op=op,
                total_machine_seconds=machine_seconds_by_op.get(op.name, 0.0),
                breaks_taken=breaks_by_op.get(op.name, 0),
                last_break_end=last_b_end,
                available_at=available_time,
                current_zone=initial_zone
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

        # Update current_zone for all operators assigned to machines
        for mach_name, op_name in machine_op.items():
            zone = self.machine_zone_map.get(mach_name, "")
            if zone:
                sim_ops[op_name].current_zone = zone

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
        # ──────────────────────────────────────────────────────────────
        # 5. Calculate break window and demand
        # ──────────────────────────────────────────────────────────────
        shift_break_win_start = shift_start + timedelta(minutes=settings.shiftBreakWindowStartOffsetMinutes)
        shift_break_win_end = shift_end - timedelta(minutes=settings.shiftBreakWindowEndOffsetMinutes)
        last_possible_start = shift_break_win_end - break_dur  # latest a break can BEGIN

        # Per-operator scheduling state (mutable during planning)
        op_sched_breaks: Dict[str, int] = {n: sim_ops[n].breaks_taken for n in sim_ops}
        op_sched_last_end: Dict[str, Optional[datetime]] = {n: sim_ops[n].last_break_end for n in sim_ops}

        # Collected break events: (start, end, op_name, machine_name|None, relief_op|None)
        break_events: List[tuple] = []
        # Track when spares are busy covering machines
        spare_busy: List[tuple] = []  # (start, end, spare_name)

        has_valid_window = last_possible_start > shift_break_win_start and settings.targetBreaksPerShift > 0

        if has_valid_window:
            # ═════════════════════════════════════════════════════
            # MODE B — STAGGERED BREAKS (has spare operators)
            # Machine operators take turns going on break.
            # Spare operators cover their machines during breaks.
            # ═════════════════════════════════════════════════════

            # --- Phase B1: Schedule machine-operator breaks ---
            total_machine_breaks = len(op_machine) * settings.targetBreaksPerShift
            max_concurrent = spare_count

            if total_machine_breaks > 0 and max_concurrent > 0:
                num_rounds = math.ceil(total_machine_breaks / max_concurrent)
                available_seconds = (last_possible_start - shift_break_win_start).total_seconds()

                # Evenly space rounds across the shift break window
                if num_rounds == 1:
                    round_times = [shift_break_win_start + timedelta(seconds=available_seconds / 2)]
                else:
                    interval = available_seconds / (num_rounds + 1)
                    round_times = [
                        shift_break_win_start + timedelta(seconds=(i + 1) * interval)
                        for i in range(num_rounds)
                    ]

                for round_time in round_times:
                    # Skip if round already finished before now
                    if round_time + break_dur <= now:
                        continue

                    # Eligible machine operators for this round
                    eligible = []
                    for op_name in op_machine:
                        remaining = settings.targetBreaksPerShift - op_sched_breaks.get(op_name, 0)
                        if remaining <= 0:
                            continue
                        last_end = op_sched_last_end.get(op_name)
                        if last_end and round_time < last_end + cooldown:
                            continue
                        if round_time + break_dur > shift_break_win_end:
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
                        machine_zone = self.machine_zone_map.get(machine_name, '')

                        # Find a qualified, available spare for relief
                        relief_op = self._find_relief(
                            machine_type, spare_ops, sim_ops, spare_busy,
                            round_time, break_dur, now=now,
                            machine_zone=machine_zone
                        )
                        if relief_op is None:
                            continue  # no qualified spare available this round

                        bs, be = round_time, round_time + break_dur
                        break_events.append((bs, be, op_name, machine_name, relief_op))
                        spare_busy.append((bs, be, relief_op))
                        # Update spare's zone to the machine they're covering
                        if machine_zone:
                            sim_ops[relief_op].current_zone = machine_zone
                        op_sched_breaks[op_name] = op_sched_breaks.get(op_name, 0) + 1
                        op_sched_last_end[op_name] = be
                        slots_filled += 1

            # --- Phase B2: Fallback for missed machine-op breaks (Un-relieved / Parked Breaks) ---
            unrelieved = [op for op in op_machine.keys() if settings.targetBreaksPerShift - op_sched_breaks.get(op, 0) > 0]
            if unrelieved:
                shift_duration = (last_possible_start - shift_break_win_start).total_seconds()
                
                groups = {}
                isolated_counter = 0
                for op in unrelieved:
                    machine_name = op_machine[op]
                    circuit = next((c.name for c in self.state.circuits if c.diggerId == machine_name or machine_name in c.truckIds), "")
                    if not circuit:
                        circuit = f"isolated_{isolated_counter}"
                        isolated_counter += 1
                    if circuit not in groups:
                        groups[circuit] = []
                    groups[circuit].append(op)
                
                group_keys = list(groups.keys())
                for i, circuit_key in enumerate(group_keys):
                    for op_name in groups[circuit_key]:
                        remaining = settings.targetBreaksPerShift - op_sched_breaks.get(op_name, 0)
                        break_index = op_sched_breaks.get(op_name, 0)
                        
                        while remaining > 0:
                            target_total = settings.targetBreaksPerShift
                            base_fraction = (break_index + 1) / (target_total + 1)
                            
                            stagger_offset = 0.0
                            if len(group_keys) > 1:
                                stagger_offset = (i / (len(group_keys) - 1)) * 0.15 - 0.075
                            
                            fraction = max(0.0, min(1.0, base_fraction + stagger_offset))
                            # Bias towards 2/3rds mark
                            fraction = (fraction + 0.66) / 2.0
                            
                            target_time = shift_break_win_start + timedelta(seconds=shift_duration * fraction)
                            
                            cursor = max(now, shift_break_win_start, sim_ops[op_name].available_at)
                            last_end = op_sched_last_end.get(op_name)
                            if last_end:
                                cursor = max(cursor, last_end + cooldown)
                            
                            # Hard BAP workstretch limit check
                            last_rest = last_end or shift_start
                            hard_limit = last_rest + timedelta(minutes=settings.maxWorkstretchMinutes)
                            
                            ideal_time = max(cursor, min(target_time, hard_limit - break_dur, last_possible_start))
                            if ideal_time > last_possible_start:
                                ideal_time = last_possible_start
                                
                            machine_name = op_machine[op_name]
                            bs, be = ideal_time, ideal_time + break_dur
                            
                            machine_type = machine_type_map.get(machine_name, '')
                            machine_zone = self.machine_zone_map.get(machine_name, '')
                            relief_op = self._find_relief(
                                machine_type, spare_ops, sim_ops, spare_busy,
                                bs, break_dur, now=now, machine_zone=machine_zone
                            )
                            
                            break_events.append((bs, be, op_name, machine_name, relief_op))
                            if relief_op:
                                spare_busy.append((bs, be, relief_op))
                                if machine_zone:
                                    sim_ops[relief_op].current_zone = machine_zone
                                    
                            op_sched_breaks[op_name] += 1
                            op_sched_last_end[op_name] = be
                            remaining -= 1
                            break_index += 1

            # --- Phase B3: Schedule standby (spare) operator breaks ---
            for spare_name in spare_ops:
                remaining = settings.targetBreaksPerShift - op_sched_breaks.get(spare_name, 0)
                while remaining > 0:
                    cursor = max(now, shift_break_win_start, sim_ops[spare_name].available_at)
                    last_end = op_sched_last_end.get(spare_name)
                    if last_end:
                        cursor = max(cursor, last_end + cooldown)

                    found = False
                    while cursor + break_dur <= shift_break_win_end:
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
                if be <= seg_start:
                    continue  # break finished before current segment start

                # If break is active right now (bs <= seg_start < be)
                if bs <= seg_start < be:
                    if relief_op:
                        planned_segments.append(PlannedSegment(
                            startTime=seg_start.isoformat(),
                            endTime=be.isoformat(),
                            operatorName=relief_op,
                            machineName=m.name,
                            segmentType="assignment"
                        ))
                    seg_start = be
                    continue

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
        # Phase 2: Determine circadian window for night shifts
        circadian_window = self._get_circadian_window(shift_start, settings)

        for bs, be, op_name, _mn, _rel in break_events:
            if be <= now:
                continue
            b_start = max(now, bs)

            # Phase 2: Variable break duration
            var_dur_minutes = self._compute_variable_break_duration(op_name, settings)
            actual_be = b_start + timedelta(minutes=var_dur_minutes)
            # Clamp to original end if variable is shorter
            actual_be = min(actual_be, be) if not settings.enableVariableBreakLength else actual_be

            # Phase 2: Determine break type
            break_type = "standard"
            if settings.enableVariableBreakLength and var_dur_minutes != settings.breakDurationMinutes:
                break_type = "variable"
            if circadian_window:
                cw_start, cw_end = circadian_window
                if cw_start <= b_start < cw_end:
                    break_type = "circadian"

            # Phase 2: Fractionable break splitting
            if settings.enableFractionableBreaks and break_type != "circadian":
                fractions = self._split_break_into_fractions(b_start, var_dur_minutes, settings)
                for frac_start, frac_end, part_idx, total_parts in fractions:
                    if frac_end <= now:
                        continue
                    planned_segments.append(PlannedSegment(
                        startTime=max(now, frac_start).isoformat(),
                        endTime=frac_end.isoformat(),
                        operatorName=op_name,
                        machineName="",
                        segmentType="break",
                        breakType="fractionable",
                        breakPartIndex=part_idx,
                        breakPartTotal=total_parts,
                    ))
            else:
                planned_segments.append(PlannedSegment(
                    startTime=b_start.isoformat(),
                    endTime=actual_be.isoformat(),
                    operatorName=op_name,
                    machineName="",
                    segmentType="break",
                    breakType=break_type,
                ))

        # Phase 2: Inject circadian forced breaks for night shifts
        if circadian_window and settings.enableCircadianScheduling:
            cw_start, cw_end = circadian_window
            if cw_start > now and cw_start < shift_end:
                for op_name in sim_ops:
                    # Check if operator already has a break in circadian window
                    has_circadian_break = any(
                        bs <= cw_start < be or (bs >= cw_start and bs < cw_end)
                        for bs, be, on, _mn, _rel in break_events if on == op_name
                    )
                    if not has_circadian_break:
                        circ_dur = settings.breakDurationMinutes
                        planned_segments.append(PlannedSegment(
                            startTime=cw_start.isoformat(),
                            endTime=(cw_start + timedelta(minutes=circ_dur)).isoformat(),
                            operatorName=op_name,
                            machineName="",
                            segmentType="break",
                            breakType="circadian",
                        ))

        planned_segments.sort(key=lambda s: s.startTime)
        return planned_segments

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────

    def _find_relief(
        self,
        machine_type: str,
        spare_ops: List[str],
        sim_ops: Dict[str, SimOperator],
        spare_busy: List[tuple],
        at_time: datetime,
        break_dur: timedelta,
        now: Optional[datetime] = None,
        machine_zone: str = ""
    ) -> Optional[str]:
        """Find a qualified spare operator available to cover a machine
        of *machine_type* during [at_time, at_time + break_dur].

        When *machine_zone* is provided, candidates are sorted
        nearest-first and travel time is added as a gap penalty so a
        spare is only considered available if they can physically reach
        the machine in time.
        """
        check_time = max(now, at_time) if now else at_time

        # Build candidate list with travel times for sorting
        candidates: List[tuple] = []  # (travel_minutes, spare_name)
        for spare_name in spare_ops:
            if machine_type not in sim_ops[spare_name].qualifications:
                continue

            # Calculate travel time from spare's current zone to target
            travel_minutes = 0
            if machine_zone:
                spare_zone = sim_ops[spare_name].current_zone
                travel_minutes = self._get_travel_time(spare_zone, machine_zone)

            travel_td = timedelta(minutes=travel_minutes)

            # Must be available (not still on their own break) accounting for travel
            if sim_ops[spare_name].available_at + travel_td > check_time:
                continue

            # Must not already be covering another machine at this time
            busy = any(
                s == spare_name
                and not (at_time + break_dur <= ss or at_time >= se)
                for ss, se, s in spare_busy
            )
            if busy:
                continue

            candidates.append((travel_minutes, spare_name))

        if not candidates:
            return None

        # Sort by travel time (nearest-first)
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]

    # ──────────────────────────────────────────────────────────────────
    # Phase 2 — BAP Helpers
    # ──────────────────────────────────────────────────────────────────

    def _compute_variable_break_duration(self, op_name: str, settings: Settings) -> int:
        """Compute break duration based on operator's fatigue level.
        Higher fatigue → longer break (up to variableBreakMaxMinutes).
        Returns duration in minutes."""
        if not settings.enableVariableBreakLength:
            return settings.breakDurationMinutes

        # Find operator's alertness from state
        op = next((o for o in self.state.operators if o.name == op_name), None)
        if op is None:
            return settings.breakDurationMinutes

        # Alertness 1.0 → min break, 0.0 → max break (linear interpolation)
        alertness = max(0.0, min(1.0, op.alertnessScore))
        min_dur = settings.variableBreakMinMinutes
        max_dur = settings.variableBreakMaxMinutes
        # Invert: low alertness → longer break
        duration = min_dur + (1.0 - alertness) * (max_dur - min_dur)
        return max(min_dur, min(max_dur, int(round(duration))))

    def _is_night_shift(self, shift_start: datetime) -> bool:
        """Check if the current shift is a night shift (starts at 19:00)."""
        return shift_start.hour >= 19 or shift_start.hour < 7

    def _get_circadian_window(self, shift_start: datetime, settings: Settings):
        """Return (window_start, window_end) datetimes for the circadian low-point,
        or None if circadian scheduling is disabled or it's a day shift."""
        if not settings.enableCircadianScheduling:
            return None
        if not self._is_night_shift(shift_start):
            return None

        try:
            start_h, start_m = map(int, settings.circadianBreakWindowStart.split(':'))
            end_h, end_m = map(int, settings.circadianBreakWindowEnd.split(':'))
        except (ValueError, AttributeError):
            return None

        # Circadian window is during the night (after midnight)
        if shift_start.hour >= 19:
            next_day = shift_start + timedelta(days=1)
            win_start = next_day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            win_end = next_day.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        else:
            win_start = shift_start.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            win_end = shift_start.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

        if win_end <= win_start:
            win_end += timedelta(days=1)

        return win_start, win_end

    def _split_break_into_fractions(self, break_start: datetime, total_duration_minutes: int,
                                     settings: Settings) -> list:
        """Split a single break into fractionable sub-breaks.
        Returns list of (start, end, part_index, total_parts) tuples."""
        if not settings.enableFractionableBreaks:
            return [(break_start, break_start + timedelta(minutes=total_duration_minutes), 0, 1)]

        num_parts = max(1, settings.fractionableBreakParts)
        min_frac = settings.minFractionDurationMinutes
        part_duration = max(min_frac, total_duration_minutes // num_parts)

        # Ensure we don't exceed total duration
        fractions = []
        cursor = break_start
        for i in range(num_parts):
            remaining_total = total_duration_minutes - (i * part_duration)
            if remaining_total <= 0:
                break
            dur = min(part_duration, remaining_total)
            frac_end = cursor + timedelta(minutes=dur)
            fractions.append((cursor, frac_end, i, num_parts))
            # Gap between sub-breaks (work period) — use half the cooldown
            gap = timedelta(minutes=max(15, settings.breakCooldownMinutes // 2))
            cursor = frac_end + gap

        return fractions if fractions else [(break_start, break_start + timedelta(minutes=total_duration_minutes), 0, 1)]
