import json
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QColor
import dateutil.parser
from .models import (
    Operator, Machine, Zone, ZoneConnection, Assignment, Break,
    AppState, Settings, PlannedSegment, ProductionTask,
    OperatorStatus, MachineStatus, CURRENT_SCHEMA_VERSION
)
from .planner import ReliefPlanner, get_shift_bounds
from .solver import SolverPlanner
from .reactive_engine import ReactiveEngine
from .telemetry import TelemetryLogger, ScheduleEvent

def merge_intervals(intervals):
    if not intervals:
        return []
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    for current in sorted_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if current[0] < prev_end:
            merged[-1] = (prev_start, max(prev_end, current[1]))
        else:
            merged.append(current)
    return merged

def format_duration_short(seconds: float) -> str:
    total_mins = int(round(seconds / 60.0))
    hours = total_mins // 60
    mins = total_mins % 60
    if hours > 0:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"

def format_operator_short_name(name: str) -> str:
    if not name:
        return ""
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0]}."
    return name


class StateManager(QObject):
    state_changed = Signal()
    time_ticked = Signal()
    
    def __init__(self, data_file="state.json"):
        super().__init__()
        self.data_file = data_file
        self.state = AppState()
        
        # Phase 3, 4, 6: New Engines
        self.solver_planner = SolverPlanner(self.state)
        self.planner = ReliefPlanner(self.state)
        self.reactive_engine = ReactiveEngine()
        self.telemetry = TelemetryLogger()
        
        # Phase 5: Production Queue
        from .production_queue import ProductionQueue
        self.production_queue = ProductionQueue()
        
        # Simulation clock controls: default to 07:00 of today, 1 min/sec (60x)
        now = datetime.now()
        self.simulated_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        self.is_paused = False
        self.speed_multiplier = 1.0  # 1.0 = 1 min/s (60x), 2.0 = 2 min/s, 4.0 = 4 min/s
        self.tick_interval_ms = 500  # 500ms resolution
        self.auto_accept_swaps = False
        
        self.load_state()
        self.recompute_plan()
        
        # Simulation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.tick_interval_ms)

    def set_auto_accept_swaps(self, enabled: bool):
        self.auto_accept_swaps = bool(enabled)
        if self.auto_accept_swaps:
            # Immediately trigger any due swaps
            if self.check_and_auto_execute_swaps(batch_mode=True):
                self.save_state()
                self.recompute_plan()
                self.state_changed.emit()

    def get_current_time(self) -> datetime:
        return self.simulated_time

    def set_simulated_time(self, dt: datetime):
        self.simulated_time = dt
        self.state.simulatedTime = dt.isoformat()
        self.recompute_plan()
        self.save_state()
        self.time_ticked.emit()
        self.state_changed.emit()

    def reset_to_start_of_shift(self):
        self.simulated_time = self.simulated_time.replace(hour=7, minute=0, second=0, microsecond=0)
        self.state.simulatedTime = self.simulated_time.isoformat()
        
        # Reset shift runtime operator metrics for a clean shift test
        for op in self.state.operators:
            op.breaksTaken = 0
            op.standbyTimeMinutes = 0
            op.cumulativeFatigueMinutes = 0.0
            op.alertnessScore = 1.0
            if op.status == 'on_break':
                op.status = 'standby'
            op.currentAssignmentId = None
                
        self.state.assignments = []
        self.state.breaks = []
        for m in self.state.machines:
            m.currentOperatorId = None

        self.recompute_plan()
        self.save_state()
        self.time_ticked.emit()
        self.state_changed.emit()

    def toggle_pause(self) -> bool:
        self.is_paused = not self.is_paused
        self.time_ticked.emit()
        return self.is_paused

    def set_paused(self, paused: bool):
        self.is_paused = paused
        self.time_ticked.emit()

    def set_speed(self, multiplier: float):
        self.speed_multiplier = max(0.1, float(multiplier))
        self.time_ticked.emit()

    @staticmethod
    def _safe_construct(cls, data_dict: dict):
        """Construct a dataclass instance, silently dropping unknown keys.
        This lets old state.json files (missing new fields) load with defaults,
        and prevents crashes if a key was removed in a newer schema."""
        import dataclasses
        known_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data_dict.items() if k in known_fields}
        return cls(**filtered)

    def load_state(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                self.state.schemaVersion = data.get('schemaVersion', 1)
                self.state.operators = [self._safe_construct(Operator, op) for op in data.get('operators', [])]
                self.state.machines = [self._safe_construct(Machine, m) for m in data.get('machines', [])]
                self.state.zones = [self._safe_construct(Zone, z) for z in data.get('zones', [])]
                self.state.zoneConnections = [self._safe_construct(ZoneConnection, zc) for zc in data.get('zoneConnections', [])]
                from .models import Circuit
                self.state.circuits = [self._safe_construct(Circuit, c) for c in data.get('circuits', [])]
                self.state.assignments = [self._safe_construct(Assignment, a) for a in data.get('assignments', [])]
                self.state.breaks = [self._safe_construct(Break, b) for b in data.get('breaks', [])]
                self.state.productionTasks = [self._safe_construct(ProductionTask, t) for t in data.get('productionTasks', [])]
                if 'settings' in data:
                    self.state.settings = self._safe_construct(Settings, data['settings'])
                
                if 'simulatedTime' in data and data['simulatedTime']:
                    try:
                        self.simulated_time = dateutil.parser.isoparse(data['simulatedTime'])
                    except Exception:
                        pass
                self.state.simulatedTime = self.simulated_time.isoformat()
                
                # Normalize legacy IDs to names
                zone_id_to_name = {z.id: z.name for z in self.state.zones}
                op_id_to_name = {o.id: o.name for o in self.state.operators}
                mach_id_to_name = {m.id: m.name for m in self.state.machines}
                
                for z in self.state.zones:
                    z.id = z.name
                for o in self.state.operators:
                    if o.currentAssignmentId in mach_id_to_name:
                        o.currentAssignmentId = mach_id_to_name[o.currentAssignmentId]
                    o.id = o.name
                for m in self.state.machines:
                    if m.zoneId in zone_id_to_name:
                        m.zoneId = zone_id_to_name[m.zoneId]
                    if m.currentOperatorId in op_id_to_name:
                        m.currentOperatorId = op_id_to_name[m.currentOperatorId]
                    m.id = m.name
                for a in self.state.assignments:
                    if a.operatorId in op_id_to_name:
                        a.operatorId = op_id_to_name[a.operatorId]
                    if a.machineId in mach_id_to_name:
                        a.machineId = mach_id_to_name[a.machineId]
                for b in self.state.breaks:
                    if b.operatorId in op_id_to_name:
                        b.operatorId = op_id_to_name[b.operatorId]
                
                # Migrate Schema Version 2 -> 3 (Create Circuits)
                if self.state.schemaVersion < 3:
                    circuit_map = {}
                    for m in data.get('machines', []):
                        grp = m.get('circuitGroup')
                        if grp:
                            if grp not in circuit_map:
                                circuit_map[grp] = {'id': grp, 'name': grp, 'diggerId': grp, 'truckIds': [], 'zoneId': m.get('zoneId', '')}
                            if m.get('type') == 'Truck':
                                circuit_map[grp]['truckIds'].append(m.get('name'))
                    for c_data in circuit_map.values():
                        self.state.circuits.append(self._safe_construct(Circuit, c_data))
                    self.state.schemaVersion = CURRENT_SCHEMA_VERSION

                # Sanitize legacy / expired open breaks
                break_dur = timedelta(minutes=self.state.settings.breakDurationMinutes)
                for b in self.state.breaks:
                    if not b.endTime:
                        try:
                            b_start = dateutil.parser.isoparse(b.startTime)
                            if b_start + break_dur <= self.simulated_time:
                                b.endTime = (b_start + break_dur).isoformat()
                        except Exception:
                            pass
                for o in self.state.operators:
                    if o.status == 'on_break':
                        has_active = any(b.operatorId == o.name and not b.endTime for b in self.state.breaks)
                        if not has_active:
                            o.status = 'standby'

                self.save_state()
                return
            except Exception as e:
                print(f"Error loading state: {e}. Falling back to default data.")

        from .models import Circuit
        # Fallback / Seed data
        self.state.operators = [
            Operator(name='Alice Smith', qualifications=['Truck', 'Water Cart']),
            Operator(name='Bob Jones', qualifications=['Digger', 'ROM Loader']),
            Operator(name='Charlie Davis', qualifications=['Truck', 'Digger'], standbyTimeMinutes=45),
            Operator(name='Diana Prince', qualifications=['Truck'], standbyTimeMinutes=80),
        ]
        self.state.zones = [
            Zone(name='North Pit'),
            Zone(name='South Pit'),
        ]
        self.state.machines = [
            Machine(name='DT-101', type='Truck', zoneId='South Pit', transitTimeMinutes=10),
            Machine(name='DT-102', type='Truck', zoneId='South Pit', transitTimeMinutes=10),
            Machine(name='EX-201', type='Digger', zoneId='South Pit', transitTimeMinutes=15),
        ]
        self.state.circuits = [
            Circuit(id='C-EX-201', name='C-EX-201', zoneId='South Pit', diggerId='EX-201', truckIds=['DT-101', 'DT-102'])
        ]
        self.state.settings = Settings()
        self.state.simulatedTime = self.simulated_time.isoformat()
        self.save_state()

    def save_state(self):
        data = {
            'schemaVersion': CURRENT_SCHEMA_VERSION,
            'operators': [op.__dict__ for op in self.state.operators],
            'machines': [m.__dict__ for m in self.state.machines],
            'zones': [z.__dict__ for z in self.state.zones],
            'zoneConnections': [zc.__dict__ for zc in self.state.zoneConnections],
            'circuits': [c.__dict__ for c in self.state.circuits],
            'assignments': [a.__dict__ for a in self.state.assignments],
            'breaks': [b.__dict__ for b in self.state.breaks],
            'productionTasks': [t.__dict__ for t in self.state.productionTasks],
            'settings': self.state.settings.__dict__,
            'simulatedTime': self.state.simulatedTime,
        }
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)


    def tick(self):
        if self.is_paused:
            return

        # Advance simulated time (step in seconds): 500ms real = 30s * speed_multiplier in simulation
        step_sim_seconds = (self.tick_interval_ms / 1000.0) * 60.0 * self.speed_multiplier
        self.simulated_time += timedelta(seconds=step_sim_seconds)
        self.state.simulatedTime = self.simulated_time.isoformat()

        step_sim_minutes = step_sim_seconds / 60.0
        settings = self.state.settings
        max_work_mins = max(1.0, float(settings.defaultOperatingTimeMinutes))

        breaks_ended = False
        # Update standby times and fatigue for operators
        for op in self.state.operators:
            if op.status == 'standby':
                op.standbyTimeMinutes = int(op.standbyTimeMinutes + step_sim_minutes)
            elif op.status == 'working':
                # ── Fatigue accumulation (§4.2) ──
                op.cumulativeFatigueMinutes += step_sim_minutes * settings.fatigueAccumulationRate
                # Alertness degrades linearly from 1.0 toward 0.0 as fatigue approaches max
                op.alertnessScore = max(0.0, 1.0 - (op.cumulativeFatigueMinutes / max_work_mins))
            elif op.status == 'on_break':
                # ── Fatigue recovery (§4.2) ──
                op.cumulativeFatigueMinutes = max(
                    0.0,
                    op.cumulativeFatigueMinutes - step_sim_minutes * settings.fatigueRecoveryRate
                )
                op.alertnessScore = max(0.0, 1.0 - (op.cumulativeFatigueMinutes / max_work_mins))

                # Check if simulated break is finished
                active_break = next((b for b in reversed(self.state.breaks) if b.operatorId == op.name and not b.endTime), None)
                if active_break:
                    try:
                        b_start = dateutil.parser.isoparse(active_break.startTime)
                        elapsed_break_sec = (self.simulated_time - b_start).total_seconds()
                        req_break_sec = settings.breakDurationMinutes * 60.0
                        if elapsed_break_sec >= req_break_sec:
                            self._end_break(op.name, active_break.id, notify=False, save=False, recompute=False)
                            breaks_ended = True
                    except Exception:
                        pass


        # Check and auto execute any due swaps if auto-accept is enabled
        swaps_executed = False
        if self.auto_accept_swaps:
            swaps_executed = self.check_and_auto_execute_swaps(batch_mode=True)

        if breaks_ended or swaps_executed:
            self.save_state()
            self.state_changed.emit()

        # Phase 4: Reactive Engine Disruption Detection
        disruptions = self.reactive_engine.detect_disruptions(self.state, self.simulated_time)
        needs_replan = self.reactive_engine.should_replan(disruptions)
        
        for d in disruptions:
            self.telemetry.log_event(ScheduleEvent(
                timestamp=self.simulated_time.isoformat(),
                event_type="DISRUPTION_DETECTED",
                operator_name=d.affected_entity if d.type in ("operator_absent", "fatigue_alert") else "",
                machine_name=d.affected_entity if d.type == "machine_down" else "",
                details={"severity": d.severity, "description": d.description}
            ))

        # Always recompute plan on tick so timeline updates dynamically, 
        # but in a real reactive system we'd use `needs_replan` to trigger the rolling horizon.
        self.recompute_plan()
        self.time_ticked.emit()

    def set_operator_absent(self, operator_name: str, absent: bool = True) -> bool:
        op = next((o for o in self.state.operators if o.name == operator_name or o.id == operator_name), None)
        if not op:
            return False
        
        if absent:
            # If operator is currently assigned to a machine, unassign
            if op.currentAssignmentId:
                m = next((mach for mach in self.state.machines if mach.name == op.currentAssignmentId or mach.id == op.currentAssignmentId), None)
                if m and m.currentOperatorId == op.name:
                    m.currentOperatorId = None
                for a in reversed(self.state.assignments):
                    if (a.operatorId == op.name or a.operatorId == op.id) and not a.endTime:
                        a.endTime = self.get_current_time().isoformat()
                        break
            op.status = 'absent'
            op.currentAssignmentId = None
            op.standbyTimeMinutes = 0
        else:
            if op.status == 'absent':
                op.status = 'standby'
                op.standbyTimeMinutes = 0
                op.currentAssignmentId = None
                
        self.save_state()
        self.recompute_plan()
        self.state_changed.emit()
        return True

    def set_machine_status(self, machine_name: str, status: str) -> bool:
        machine = next((m for m in self.state.machines if m.name == machine_name or m.id == machine_name), None)
        if not machine:
            return False
            
        machine.status = status
        if status != 'operational' and machine.currentOperatorId:
            op = next((o for o in self.state.operators if o.name == machine.currentOperatorId or o.id == machine.currentOperatorId), None)
            if op:
                op.status = 'standby'
                op.currentAssignmentId = None
            for a in reversed(self.state.assignments):
                if (a.machineId == machine.name or a.machineId == machine.id) and not a.endTime:
                    a.endTime = self.get_current_time().isoformat()
                    break
            machine.currentOperatorId = None
            
        self.save_state()
        self.recompute_plan()
        self.state_changed.emit()
        return True

    def apply_daily_allocation(
        self,
        allocations: Dict[str, Optional[str]],
        absent_operator_names: List[str],
        not_required_machine_names: List[str],
        reset_shift_time: bool = True,
        reset_metrics: bool = True
    ) -> bool:
        now = self.simulated_time
        if reset_shift_time:
            self.simulated_time = self.simulated_time.replace(hour=7, minute=0, second=0, microsecond=0)
            self.state.simulatedTime = self.simulated_time.isoformat()
            now = self.simulated_time

        # 1. Reset runtime shift metrics & records
        if reset_metrics or reset_shift_time:
            self.state.assignments = []
            self.state.breaks = []
            for op in self.state.operators:
                op.breaksTaken = 0
                op.standbyTimeMinutes = 0
                op.cumulativeFatigueMinutes = 0.0
                op.alertnessScore = 1.0
                op.currentAssignmentId = None
                op.status = 'standby'
            for m in self.state.machines:
                m.currentOperatorId = None

        absent_set = set(absent_operator_names)
        not_required_set = set(not_required_machine_names)

        # 2. Update Machine statuses & initial operator mappings
        for m in self.state.machines:
            if m.name in not_required_set or m.id in not_required_set:
                m.status = 'not_required'
                m.currentOperatorId = None
            else:
                m.status = 'operational'
                assigned_op = allocations.get(m.name, allocations.get(m.id, None))
                if assigned_op and assigned_op not in absent_set:
                    m.currentOperatorId = assigned_op
                else:
                    m.currentOperatorId = None

        # 3. Update Operator statuses & establish starting assignments
        assigned_ops_map = {m.currentOperatorId: m.name for m in self.state.machines if m.status == 'operational' and m.currentOperatorId}

        for op in self.state.operators:
            if op.name in absent_set or op.id in absent_set:
                op.status = 'absent'
                op.currentAssignmentId = None
                op.standbyTimeMinutes = 0
            elif op.name in assigned_ops_map:
                mach_name = assigned_ops_map[op.name]
                op.status = 'working'
                op.currentAssignmentId = mach_name
                op.standbyTimeMinutes = 0
                self.state.assignments.append(Assignment(
                    id=f"a_{now.timestamp()}_{op.name.replace(' ', '_')}",
                    operatorId=op.name,
                    machineId=mach_name,
                    startTime=now.isoformat()
                ))
            else:
                op.status = 'standby'
                op.currentAssignmentId = None
                op.standbyTimeMinutes = 0

        self.save_state()
        self.recompute_plan()
        self.time_ticked.emit()
        self.state_changed.emit()
        return True

    def move_machine_to_zone(self, machine_name: str, target_zone_name: str):
        machine = next((m for m in self.state.machines if m.name == machine_name or m.id == machine_name), None)
        if machine:
            machine.zoneId = target_zone_name
            self.save_state()
            self.recompute_plan()
            self.state_changed.emit()
            return True
        return False

    def assign_operator(self, operator_id: str, machine_id: str, notify: bool = True, save: bool = True, recompute: bool = True):
        op = next((o for o in self.state.operators if o.id == operator_id or o.name == operator_id), None)
        machine = next((m for m in self.state.machines if m.id == machine_id or m.name == machine_id), None)
        
        if not op or not machine:
            return False
            
        if machine.type not in op.qualifications:
            print(f"Operator {op.name} not qualified for {machine.type}")
            return False

        # Close out previous assignment for machine
        if machine.currentOperatorId:
            prev_op = next((o for o in self.state.operators if o.id == machine.currentOperatorId or o.name == machine.currentOperatorId), None)
            if prev_op:
                prev_op.status = 'standby'
                prev_op.currentAssignmentId = None
            
            for a in reversed(self.state.assignments):
                if (a.machineId == machine.id or a.machineId == machine.name) and not a.endTime:
                    a.endTime = self.get_current_time().isoformat()
                    break

        # Close out previous assignment for operator
        if op.currentAssignmentId:
            prev_machine = next((m for m in self.state.machines if m.id == op.currentAssignmentId or m.name == op.currentAssignmentId), None)
            if prev_machine:
                prev_machine.currentOperatorId = None
            
            for a in reversed(self.state.assignments):
                if (a.operatorId == op.id or a.operatorId == op.name) and not a.endTime:
                    a.endTime = self.get_current_time().isoformat()
                    break

        op.status = 'working'
        op.standbyTimeMinutes = 0
        op.currentAssignmentId = machine.name
        machine.currentOperatorId = op.name

        new_assignment = Assignment(
            id=f"a_{self.get_current_time().timestamp()}",
            operatorId=op.name,
            machineId=machine.name,
            startTime=self.get_current_time().isoformat()
        )
        self.state.assignments.append(new_assignment)
        
        if save:
            self.save_state()
        if recompute:
            self.recompute_plan()
        if notify:
            self.state_changed.emit()
        return True

    def send_on_break(self, operator_id: str, notify: bool = True, save: bool = True, recompute: bool = True):
        op = next((o for o in self.state.operators if o.id == operator_id or o.name == operator_id), None)
        if not op:
            return

        if op.currentAssignmentId:
            machine = next((m for m in self.state.machines if m.id == op.currentAssignmentId or m.name == op.currentAssignmentId), None)
            if machine:
                machine.currentOperatorId = None
            
            for a in reversed(self.state.assignments):
                if (a.operatorId == op.id or a.operatorId == op.name) and not a.endTime:
                    a.endTime = self.get_current_time().isoformat()
                    break

        op.status = 'on_break'
        op.currentAssignmentId = None
        op.breaksTaken += 1

        new_break = Break(
            id=f"b_{self.get_current_time().timestamp()}",
            operatorId=op.name,
            startTime=self.get_current_time().isoformat()
        )
        self.state.breaks.append(new_break)
        
        if save:
            self.save_state()
        if recompute:
            self.recompute_plan()
        if notify:
            self.state_changed.emit()

    def get_pending_swap_for_machine(self, machine_name: str) -> Optional[Dict]:
        """Check if machine has a planned swap / relief / break pending confirmation at current time."""
        machine = next((m for m in self.state.machines if m.name == machine_name or m.id == machine_name), None)
        if not machine or machine.status != 'operational':
            return None

        now = self.get_current_time()
        curr_op = machine.currentOperatorId

        # Check planned segments for this machine
        m_segs = [s for s in self.state.plannedSegments if s.machineName == machine.name and s.segmentType == 'assignment']
        b_segs = [s for s in self.state.plannedSegments if s.segmentType == 'break']

        # Look for an active planned assignment at now
        active_assign = None
        for s in m_segs:
            try:
                s_start = dateutil.parser.isoparse(s.startTime)
                s_end = dateutil.parser.isoparse(s.endTime)
                if s_start <= now < s_end:
                    active_assign = (s, s_start, s_end)
                    break
            except Exception:
                pass

        if active_assign:
            planned_seg, s_start, s_end = active_assign
            planned_op = planned_seg.operatorName

            if planned_op != curr_op:
                # Check if current operator has a planned break starting around now
                curr_op_break = False
                if curr_op:
                    for bs in b_segs:
                        if bs.operatorName == curr_op:
                            try:
                                bs_start = dateutil.parser.isoparse(bs.startTime)
                                bs_end = dateutil.parser.isoparse(bs.endTime)
                                if bs_start <= now < bs_end:
                                    curr_op_break = True
                                    break
                            except Exception:
                                pass

                if curr_op and curr_op_break:
                    return {
                        'machine_name': machine.name,
                        'type': 'relief_swap',
                        'outgoing_op': curr_op,
                        'incoming_op': planned_op,
                        'label': f"⇄ Relieve: {format_operator_short_name(planned_op)}",
                        'tooltip': f"Send {curr_op} on break & hand over {machine.name} to {planned_op}",
                        'start_time': s_start,
                        'end_time': s_end
                    }
                elif curr_op:
                    return {
                        'machine_name': machine.name,
                        'type': 'operator_swap',
                        'outgoing_op': curr_op,
                        'incoming_op': planned_op,
                        'label': f"⇄ Swap: {format_operator_short_name(planned_op)}",
                        'tooltip': f"Swap operator on {machine.name} to {planned_op}",
                        'start_time': s_start,
                        'end_time': s_end
                    }
                else:
                    return {
                        'machine_name': machine.name,
                        'type': 'assign_operator',
                        'outgoing_op': None,
                        'incoming_op': planned_op,
                        'label': f"🚜 Assign: {format_operator_short_name(planned_op)}",
                        'tooltip': f"Assign {planned_op} to {machine.name}",
                        'start_time': s_start,
                        'end_time': s_end
                    }
            return None

        # No active planned assignment at now (e.g. machine scheduled to park / synchronized break)
        if curr_op:
            for bs in b_segs:
                if bs.operatorName == curr_op:
                    try:
                        bs_start = dateutil.parser.isoparse(bs.startTime)
                        bs_end = dateutil.parser.isoparse(bs.endTime)
                        if bs_start <= now < bs_end:
                            return {
                                'machine_name': machine.name,
                                'type': 'send_break',
                                'outgoing_op': curr_op,
                                'incoming_op': None,
                                'label': f"☕ Break: {format_operator_short_name(curr_op)}",
                                'tooltip': f"Send {curr_op} on break & park {machine.name}",
                                'start_time': bs_start,
                                'end_time': bs_end
                            }
                    except Exception:
                        pass

        return None

    def execute_pending_swap(self, machine_name: str, notify: bool = True, save: bool = True, recompute: bool = True) -> bool:
        """Execute the pending swap/break transition for a machine."""
        swap = self.get_pending_swap_for_machine(machine_name)
        if not swap:
            return False

        outgoing_op = swap.get('outgoing_op')
        incoming_op = swap.get('incoming_op')
        swap_type = swap.get('type')

        if swap_type == 'relief_swap':
            if outgoing_op:
                self.send_on_break(outgoing_op, notify=False, save=False, recompute=False)
            if incoming_op:
                self.assign_operator(incoming_op, machine_name, notify=False, save=False, recompute=False)
        elif swap_type == 'send_break':
            if outgoing_op:
                self.send_on_break(outgoing_op, notify=False, save=False, recompute=False)
        elif swap_type in ('operator_swap', 'assign_operator'):
            if incoming_op:
                self.assign_operator(incoming_op, machine_name, notify=False, save=False, recompute=False)

        if save:
            self.save_state()
        if recompute:
            self.recompute_plan()
        if notify:
            self.state_changed.emit()

        return True

    def check_and_auto_execute_swaps(self, batch_mode: bool = False) -> bool:
        """Check all machines and standby operators for due swaps/breaks and auto-execute them.
        Returns True if any swap or break was executed."""
        if not self.auto_accept_swaps:
            return False

        any_executed = False

        # 1. Operational machines pending swaps
        for m in list(self.state.machines):
            if m.status == 'operational':
                swap = self.get_pending_swap_for_machine(m.name)
                if swap:
                    if batch_mode:
                        if self.execute_pending_swap(m.name, notify=False, save=False, recompute=False):
                            any_executed = True
                    else:
                        if self.execute_pending_swap(m.name):
                            any_executed = True

        # 2. Standby operators scheduled for break
        now = self.get_current_time()
        for op in list(self.state.operators):
            if op.status == 'standby':
                for bs in self.state.plannedSegments:
                    if bs.operatorName == op.name and bs.segmentType == 'break':
                        try:
                            bs_start = dateutil.parser.isoparse(bs.startTime)
                            bs_end = dateutil.parser.isoparse(bs.endTime)
                            if bs_start <= now <= bs_end:
                                if batch_mode:
                                    self.send_on_break(op.name, notify=False, save=False, recompute=False)
                                else:
                                    self.send_on_break(op.name)
                                any_executed = True
                                break
                        except Exception as e:
                            print(f"Error executing swap: {e}")

        return any_executed
            
    def get_circadian_window(self) -> Optional[tuple[datetime, datetime]]:
        """Returns the (start, end) of the circadian window for the current shift, if applicable."""
        if not self.state.settings.enableCircadianScheduling:
            return None
        now = self.get_current_time()
        shift_start, _ = get_shift_bounds(now)
        # We can borrow the planner's helper since it's already there
        # For solver planner we could add it, but it's identical logic so we just use the heuristic planner's helper
        from .planner import ReliefPlanner
        return ReliefPlanner._get_circadian_window(shift_start, self.state.settings)

    def get_locked_horizon(self) -> Optional[tuple[datetime, datetime]]:
        """Returns the (start, end) of the locked horizon where reactive planner shouldn't move segments."""
        if not self.state.settings.autoPlanEnabled:
            return None
        now = self.get_current_time()
        end = now + timedelta(minutes=self.state.settings.lockedHorizonMinutes)
        return (now, end)

    def recompute_plan(self):
        if self.state.settings.autoPlanEnabled:
            now = self.get_current_time()
            
            # Phase 3: Use SolverPlanner if enabled, otherwise ReliefPlanner
            if self.state.settings.useAdvancedSolver:
                self.solver_planner.state = self.state
                self.state.plannedSegments = self.solver_planner.generate_plan(now)
            else:
                self.planner.state = self.state
                self.state.plannedSegments = self.planner.generate_plan(now)
            
            # Phase 6: Telemetry logging
            self.telemetry.log_event(ScheduleEvent(
                timestamp=now.isoformat(),
                event_type="REPLAN_TRIGGERED",
                operator_name="SYSTEM",
                machine_name="SYSTEM",
                details={"segments_generated": len(self.state.plannedSegments)}
            ))
        else:
            self.state.plannedSegments = []

    def get_machine_segments(self, machine_name: str) -> list:
        now = self.get_current_time()
        segments = []

        # 1. Historical and current active assignments
        assignments = [
            a for a in self.state.assignments
            if a.machineId == machine_name
        ]
        for a in assignments:
            op = next(
                (o for o in self.state.operators if o.name == a.operatorId or o.id == a.operatorId),
                None
            )
            try:
                start_dt = dateutil.parser.isoparse(a.startTime)
                end_dt = dateutil.parser.isoparse(a.endTime) if a.endTime else now
                op_label = format_operator_short_name(op.name) if op else "Unknown"
                segments.append({
                    'start': start_dt,
                    'end': end_dt,
                    'label': op_label,
                    'color': QColor("#059669"), # Emerald 600
                    'is_planned': False
                })
            except Exception:
                pass

        # 2. Future planned segments
        if self.state.settings.autoPlanEnabled:
            planned = [
                p for p in self.state.plannedSegments
                if p.machineName == machine_name and p.segmentType == "assignment"
            ]
            for p in planned:
                try:
                    start_dt = dateutil.parser.isoparse(p.startTime)
                    end_dt = dateutil.parser.isoparse(p.endTime)
                    p_op_label = format_operator_short_name(p.operatorName)
                    segments.append({
                        'start': start_dt,
                        'end': end_dt,
                        'label': f"(Plan) {p_op_label}",
                        'color': QColor("#10b981"), # Emerald 500
                        'is_planned': True
                    })
                except Exception:
                    pass

        return segments

    def get_operator_shift_stats(self, operator_name: str, now: Optional[datetime] = None) -> dict:
        if now is None:
            now = self.get_current_time()
        shift_start, shift_end = get_shift_bounds(now)
        effective_now = min(shift_end, max(shift_start, now))
        
        machine_seconds = 0.0
        break_seconds = 0.0
        
        # 1. Historical machine operating seconds
        for a in self.state.assignments:
            if a.operatorId == operator_name:
                try:
                    a_start = max(shift_start, dateutil.parser.isoparse(a.startTime))
                    a_end = min(effective_now, dateutil.parser.isoparse(a.endTime)) if a.endTime else effective_now
                    if a_end > a_start:
                        machine_seconds += (a_end - a_start).total_seconds()
                except Exception:
                    pass

        # 2. Historical break seconds
        break_dur = timedelta(minutes=self.state.settings.breakDurationMinutes)
        for b in self.state.breaks:
            if b.operatorId == operator_name:
                try:
                    b_start = max(shift_start, dateutil.parser.isoparse(b.startTime))
                    max_end_dt = b_start + break_dur
                    if b.endTime:
                        b_end = min(effective_now, dateutil.parser.isoparse(b.endTime), max_end_dt)
                    else:
                        b_end = min(effective_now, max_end_dt)
                    if b_end > b_start:
                        break_seconds += (b_end - b_start).total_seconds()
                except Exception:
                    pass

        op = next((o for o in self.state.operators if o.name == operator_name or o.id == operator_name), None)
        breaks_taken = op.breaksTaken if op else 0
        status = op.status if op else 'standby'
        current_machine = op.currentAssignmentId if (op and op.status == 'working') else None
        standby_minutes = op.standbyTimeMinutes if op else 0

        if status == 'absent':
            standby_seconds = 0.0
            total_work_seconds = machine_seconds
        else:
            elapsed_shift_seconds = max(0.0, (effective_now - shift_start).total_seconds())
            standby_seconds = max(0.0, elapsed_shift_seconds - machine_seconds - break_seconds)
            total_work_seconds = machine_seconds + standby_seconds

        return {
            'machine_seconds': machine_seconds,
            'standby_seconds': standby_seconds,
            'break_seconds': break_seconds,
            'total_work_seconds': total_work_seconds,
            'machine_str': format_duration_short(machine_seconds),
            'standby_str': format_duration_short(standby_seconds),
            'break_str': format_duration_short(break_seconds),
            'work_str': format_duration_short(total_work_seconds),
            'breaks_taken': breaks_taken,
            'status': status,
            'current_machine': current_machine,
            'standby_minutes': standby_minutes,
            # ── Phase 1: Fatigue stats ──
            'alertness_score': op.alertnessScore if op else 1.0,
            'cumulative_fatigue_minutes': op.cumulativeFatigueMinutes if op else 0.0,
            'competency_multipliers': op.competencyMultipliers if op else {},
        }

    def get_operator_segments(self, operator_name: str) -> list:
        op = next((o for o in self.state.operators if o.name == operator_name or o.id == operator_name), None)
        if op and op.status == 'absent':
            return []
        now = self.get_current_time()
        shift_start, shift_end = get_shift_bounds(now)
        effective_now = min(shift_end, max(shift_start, now))
        segments = []

        # --- 1. Historical Actual Intervals (shift_start to effective_now) ---
        actual_busy_intervals = []

        # Actual machine assignments
        assignments = [
            a for a in self.state.assignments
            if a.operatorId == operator_name
        ]
        for a in assignments:
            m = next(
                (mac for mac in self.state.machines if mac.name == a.machineId or mac.id == a.machineId),
                None
            )
            try:
                start_dt = max(shift_start, dateutil.parser.isoparse(a.startTime))
                end_dt = min(effective_now, dateutil.parser.isoparse(a.endTime)) if a.endTime else effective_now
                if end_dt > start_dt:
                    segments.append({
                        'start': start_dt,
                        'end': end_dt,
                        'label': m.name if m else "Machine",
                        'color': QColor("#0ea5e9"), # Sky 500
                        'is_planned': False
                    })
                    actual_busy_intervals.append((start_dt, end_dt))
            except Exception:
                pass

        # Actual breaks
        break_dur = timedelta(minutes=self.state.settings.breakDurationMinutes)
        breaks = [
            b for b in self.state.breaks
            if b.operatorId == operator_name
        ]
        for b in breaks:
            try:
                start_dt = max(shift_start, dateutil.parser.isoparse(b.startTime))
                max_end_dt = start_dt + break_dur
                if b.endTime:
                    end_dt = min(effective_now, dateutil.parser.isoparse(b.endTime), max_end_dt)
                else:
                    end_dt = min(effective_now, max_end_dt)
                if end_dt > start_dt:
                    segments.append({
                        'start': start_dt,
                        'end': end_dt,
                        'label': "Break",
                        'color': QColor("#8b5cf6"), # Violet 500
                        'is_planned': False
                    })
                    actual_busy_intervals.append((start_dt, end_dt))
            except Exception:
                pass

        # Actual Standby / Spare gaps in [shift_start, effective_now]
        merged_actual = merge_intervals(actual_busy_intervals)
        cursor = shift_start
        for b_start, b_end in merged_actual:
            if b_start > cursor:
                segments.append({
                    'start': cursor,
                    'end': b_start,
                    'label': "Standby",
                    'color': QColor("#d97706"), # Amber 600
                    'is_planned': False
                })
            cursor = max(cursor, b_end)
        if cursor < effective_now:
            segments.append({
                'start': cursor,
                'end': effective_now,
                'label': "Standby",
                'color': QColor("#d97706"), # Amber 600
                'is_planned': False
            })

        # --- 2. Future Planned Intervals (effective_now to shift_end) ---
        if self.state.settings.autoPlanEnabled and effective_now < shift_end:
            planned_busy_intervals = []
            planned = [
                p for p in self.state.plannedSegments
                if p.operatorName == operator_name
            ]
            for p in planned:
                try:
                    start_dt = max(effective_now, dateutil.parser.isoparse(p.startTime))
                    end_dt = min(shift_end, dateutil.parser.isoparse(p.endTime))
                    if end_dt > start_dt:
                        if p.segmentType == "assignment":
                            segments.append({
                                'start': start_dt,
                                'end': end_dt,
                                'label': f"(Plan) {p.machineName}",
                                'color': QColor("#38bdf8"), # Sky 400
                                'is_planned': True
                            })
                            planned_busy_intervals.append((start_dt, end_dt))
                        elif p.segmentType == "break":
                            label = "(Plan) Break"
                            b_type = getattr(p, 'breakType', 'standard')
                            if b_type == 'fractionable':
                                label += f" {getattr(p, 'breakPartIndex', 1)}/{getattr(p, 'breakPartTotal', 1)}"
                            
                            color = QColor("#a78bfa") # Violet 400
                            if b_type == 'circadian':
                                color = QColor("#c084fc") # Fuchsia 400
                                label = "Night Break"
                                
                            segments.append({
                                'start': start_dt,
                                'end': end_dt,
                                'label': label,
                                'color': color,
                                'is_planned': True,
                                'break_type': b_type
                            })
                            planned_busy_intervals.append((start_dt, end_dt))
                except Exception:
                    pass

            # Planned Standby / Spare gaps in [effective_now, shift_end]
            merged_planned = merge_intervals(planned_busy_intervals)
            plan_cursor = effective_now
            for p_start, p_end in merged_planned:
                if p_start > plan_cursor:
                    segments.append({
                        'start': plan_cursor,
                        'end': p_start,
                        'label': "(Plan) Standby",
                        'color': QColor("#f59e0b"), # Amber 500
                        'is_planned': True
                    })
                plan_cursor = max(plan_cursor, p_end)
            if plan_cursor < shift_end:
                segments.append({
                    'start': plan_cursor,
                    'end': shift_end,
                    'label': "(Plan) Standby",
                    'color': QColor("#f59e0b"), # Amber 500
                    'is_planned': True
                })

        segments.sort(key=lambda s: s['start'])
        return segments

    def _end_break(self, operator_id: str, break_id: str, notify: bool = True, save: bool = True, recompute: bool = True):
        op = next((o for o in self.state.operators if o.id == operator_id or o.name == operator_id), None)
        b = next((b for b in self.state.breaks if b.id == break_id), None)
        if op and op.status == 'on_break':
            op.status = 'standby'
        if b:
            b.endTime = self.get_current_time().isoformat()
        
        if save:
            self.save_state()
        if recompute:
            self.recompute_plan()
        if notify:
            self.state_changed.emit()

    def get_travel_time(self, start_zone: str, target_zone: str) -> int:
        if start_zone == target_zone:
            return 0
            
        import heapq
        import math
        
        zone_map = {z.id: z for z in self.state.zones}
        
        if start_zone not in zone_map or target_zone not in zone_map:
            return 0 # Fallback
            
        PIXELS_PER_MINUTE = 10.0
        graph = {z.id: {} for z in self.state.zones}
        
        # Build adjacency list with Euclidean defaults
        for z1 in self.state.zones:
            for z2 in self.state.zones:
                if z1.id != z2.id:
                    dist = math.hypot(z2.x - z1.x, z2.y - z1.y)
                    time = int(dist / PIXELS_PER_MINUTE)
                    graph[z1.id][z2.id] = time
            
        for conn in self.state.zoneConnections:
            if conn.zone_a in graph and conn.zone_b in graph:
                # Undirected graph assuming travel time is symmetric
                graph[conn.zone_a][conn.zone_b] = conn.travelTimeMinutes
                graph[conn.zone_b][conn.zone_a] = conn.travelTimeMinutes
            
        distances = {node: float('infinity') for node in graph}
        distances[start_zone] = 0
        pq = [(0, start_zone)]
        
        while pq:
            current_dist, current_node = heapq.heappop(pq)
            
            if current_node == target_zone:
                return int(current_dist)
                
            if current_dist > distances[current_node]:
                continue
                
            for neighbor, weight in graph[current_node].items():
                distance = current_dist + weight
                if distance < distances.get(neighbor, float('infinity')):
                    distances[neighbor] = distance
                    heapq.heappush(pq, (distance, neighbor))
                    
        return 0 # Unreachable

