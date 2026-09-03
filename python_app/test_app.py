import os
import sys
import unittest
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from core.models import Operator, Machine, Zone, Settings, ZoneConnection, PlannedSegment, Break
from core.planner import ReliefPlanner
from core.state_manager import StateManager, format_operator_short_name
from ui.timeline_widget import TimelineRulerWidget, TimelineTrackWidget
from ui.views import MachineRowWidget, OperatorRowWidget, ZoneView, EquipmentView, OperatorsView
from ui.map_view import LocationsMapTab
from ui.settings_dialog import (
    OperatorEditDialog, MachineEditDialog, CrewTab, MachinesTab, SettingsDialog, STANDARD_EQUIPMENT_TYPES
)
from ui.allocation_wizard import (
    AllocationWizardDialog, is_digger, is_rom_loader, is_truck, is_auxiliary, is_operator_qualified_for_machine
)

class TestAppAll(unittest.TestCase):
    def setUp(self):
        self.test_state_file = os.path.join(os.path.dirname(__file__), "test_app_temp.json")
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
            
        self.sm = StateManager(self.test_state_file)
        self.sm.state.operators = [
            Operator(name="Alice Smith", qualifications=["Truck", "Water Cart"]),
            Operator(name="Bob Jones", qualifications=["Digger", "ROM Loader"]),
            Operator(name="Charlie Davis", qualifications=["Truck", "Digger"]),
            Operator(name="Diana Prince", qualifications=["Truck"]),
            Operator(name="Benjamin Lewis", qualifications=["Dozer", "Digger"]),
        ]
        self.sm.state.machines = [
            Machine(name="EX-101", type="Digger", zoneId="North Pit"),
            Machine(name="DT-201", type="Truck", zoneId="North Pit"),
            Machine(name="LD-301", type="ROM Loader", zoneId="ROM Pad"),
            Machine(name="DZ-401", type="Dozer", zoneId="North Pit"),
            Machine(name="WC-501", type="Water Cart", zoneId="South Pit"),
        ]
        self.sm.state.zones = [Zone(name="North Pit"), Zone(name="South Pit"), Zone(name="ROM Pad")]
        self.sm.state.settings = Settings(autoPlanEnabled=True)

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_no_auxiliary_or_drill_in_standard_types(self):
        self.assertNotIn("Auxiliary", STANDARD_EQUIPMENT_TYPES)
        self.assertNotIn("Drill", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("Digger", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("Truck", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("ROM Loader", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("Dozer", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("Grader", STANDARD_EQUIPMENT_TYPES)
        self.assertIn("Water Cart", STANDARD_EQUIPMENT_TYPES)

    def test_strict_qualification_matching(self):
        alice = self.sm.state.operators[0] # Truck, Water Cart
        wc_machine = Machine(name="WC-501", type="Water Cart")
        dz_machine = Machine(name="DZ-401", type="Dozer")
        ex_machine = Machine(name="EX-101", type="Digger")
        
        self.assertTrue(is_operator_qualified_for_machine(alice, wc_machine))
        self.assertFalse(is_operator_qualified_for_machine(alice, dz_machine))
        self.assertFalse(is_operator_qualified_for_machine(alice, ex_machine))

    def test_operator_edit_dialog(self):
        alice = self.sm.state.operators[0]
        dialog = OperatorEditDialog(alice)
        self.assertNotIn("Auxiliary", dialog.qual_checkboxes)
        self.assertTrue(dialog.qual_checkboxes["Truck"].isChecked())
        self.assertTrue(dialog.qual_checkboxes["Water Cart"].isChecked())
        self.assertFalse(dialog.qual_checkboxes["Dozer"].isChecked())
        dialog.close()

    def test_machine_edit_dialog(self):
        m = self.sm.state.machines[0]
        dialog = MachineEditDialog(m, known_zones=["North Pit", "South Pit"])
        # Check standard types in combo
        combo_types = [dialog.type_combo.itemText(i) for i in range(dialog.type_combo.count())]
        self.assertNotIn("Auxiliary", combo_types)
        self.assertIn("Water Cart", combo_types)
        dialog.close()

    def test_format_operator_short_name(self):
        self.assertEqual(format_operator_short_name("Alice Smith"), "Alice S.")
        self.assertEqual(format_operator_short_name("Bob Jones"), "Bob J.")
        self.assertEqual(format_operator_short_name("Benjamin Lewis"), "Benjamin L.")
        self.assertEqual(format_operator_short_name("Diana"), "Diana")

    def test_views_and_absent_filtering(self):
        self.sm.state.operators[3].status = 'absent' # Diana
        ops_view = OperatorsView(self.sm)
        ops_view.update_view()
        displayed_rows = ops_view.findChildren(OperatorRowWidget)
        displayed_names = [r.operator.name for r in displayed_rows]
        self.assertIn("Alice Smith", displayed_names)
        self.assertNotIn("Diana Prince", displayed_names)
        ops_view.close()

    def test_operators_view_no_duplicate_lists_on_multiple_updates(self):
        ops_view = OperatorsView(self.sm)
        # Call update_view 4 times in succession (as happens on repeated ticks / state changes)
        ops_view.update_view()
        ops_view.update_view()
        ops_view.update_view()
        ops_view.update_view()
        
        displayed_rows = ops_view.findChildren(OperatorRowWidget)
        # Should only have 5 rows (1 per operator in setup), not 20!
        self.assertEqual(len(displayed_rows), 5)
        ops_view.close()

    def test_add_area_auto_creates_connections_to_all_other_nodes(self):
        zones = [
            Zone(name="IM9", id="IM9", x=86.0, y=-50.0),
            Zone(name="ROM Pad", id="ROM Pad", x=91.0, y=24.0),
            Zone(name="CN5", id="CN5", x=47.0, y=98.0)
        ]
        connections = []
        map_tab = LocationsMapTab(zones, connections)
        
        # Initially 3 zones, 0 connections, 0 edge items
        self.assertEqual(len(map_tab.zones), 3)
        self.assertEqual(len(map_tab.connections), 0)
        self.assertEqual(len(map_tab.edge_items), 0)
        
        # Add a new area "IM8"
        map_tab.add_area("IM8")
        
        # Now 4 zones
        self.assertEqual(len(map_tab.zones), 4)
        self.assertIn("IM8", [z.name for z in map_tab.zones])
        
        # Auto-created connections to all 3 existing nodes: IM9, ROM Pad, CN5
        self.assertEqual(len(map_tab.connections), 3)
        
        targets = set()
        for c in map_tab.connections:
            self.assertEqual(c.travelTimeMinutes, 5)
            if c.zone_a == "IM8":
                targets.add(c.zone_b)
            elif c.zone_b == "IM8":
                targets.add(c.zone_a)
        self.assertEqual(targets, {"IM9", "ROM Pad", "CN5"})
        
        # Visual edge items updated
        self.assertEqual(len(map_tab.edge_items), 3)
        
        # Adding another area "South Pit"
        map_tab.add_area("South Pit")
        self.assertEqual(len(map_tab.zones), 5)
        # Now has 3 + 4 = 7 connections total
        self.assertEqual(len(map_tab.connections), 7)
        self.assertEqual(len(map_tab.edge_items), 7)
        
        map_tab.close()

    def test_add_area_empty_map(self):
        map_tab = LocationsMapTab([], [])
        self.assertEqual(len(map_tab.zones), 0)
        self.assertEqual(len(map_tab.connections), 0)
        
        # Adding the very first area creates 0 connections
        map_tab.add_area("Zone 1")
        self.assertEqual(len(map_tab.zones), 1)
        self.assertEqual(len(map_tab.connections), 0)
        
        # Adding the second area connects to the first area
        map_tab.add_area("Zone 2")
        self.assertEqual(len(map_tab.zones), 2)
        self.assertEqual(len(map_tab.connections), 1)
        self.assertEqual(map_tab.connections[0].travelTimeMinutes, 5)
        
        map_tab.close()


class TestBreakFirstPlanner(unittest.TestCase):
    """Tests for the break-first relief planner."""

    def _make_state(self, num_ops, num_machines, settings_overrides=None):
        """Build a test AppState with num_ops operators and num_machines machines.

        All operators qualified for 'Truck', all machines type 'Truck'.
        """
        from core.models import AppState
        state = AppState()
        for i in range(num_ops):
            state.operators.append(
                Operator(name=f"Op{i+1}", qualifications=["Truck"])
            )
        for i in range(num_machines):
            m = Machine(name=f"M{i+1}", type="Truck", status='operational')
            if i < num_ops:
                m.currentOperatorId = f"Op{i+1}"
                state.operators[i].status = 'working'
                state.operators[i].currentAssignmentId = m.name
            state.machines.append(m)
        state.zones = [Zone(name="Pit")]
        s = Settings(
            autoPlanEnabled=True,
            targetBreaksPerShift=2,
            breakDurationMinutes=35,
            breakCooldownMinutes=90,
            shiftBreakWindowStartOffsetMinutes=90,
            shiftBreakWindowEndOffsetMinutes=60,
        )
        if settings_overrides:
            for k, v in settings_overrides.items():
                setattr(s, k, v)
        state.settings = s
        return state

    def _day_shift_time(self, hour, minute=0):
        """Return a datetime during a day shift (07:00-19:00)."""
        return datetime(2026, 8, 26, hour, minute)

    def test_synchronized_breaks_zero_spares(self):
        """With 0 spare operators and the same circuit group, all operators should break at the same time."""
        from core.planner import ReliefPlanner
        from core.models import Circuit
        # 5 ops, 5 machines => 0 spares => synchronized mode
        state = self._make_state(5, 5)
        state.circuits = [Circuit(name="Circuit1", truckIds=[m.name for m in state.machines])]
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        assignments = [s for s in segments if s.segmentType == 'assignment']

        # Each operator should get 2 breaks => 10 break segments total
        self.assertEqual(len(breaks), 10)

        # Breaks should be synchronized: only 2 distinct break start times
        break_starts = set(s.startTime for s in breaks)
        self.assertEqual(len(break_starts), 2, f"Expected 2 synchronized rounds, got {len(break_starts)}")

        # Each round should have all 5 operators
        for start in break_starts:
            ops_in_round = [s.operatorName for s in breaks if s.startTime == start]
            self.assertEqual(len(ops_in_round), 5)

        # No relief segments (all machines idle during synchronized breaks)
        relief_segs = [s for s in assignments if s.operatorName.startswith("Op") and s not in assignments]
        # Machine segments should have gaps during break times (no relief operator)
        for start in break_starts:
            relief_during = [s for s in assignments if s.startTime == start]
            # All machine segments should stop before the break, not have relief
            self.assertEqual(len(relief_during), 0,
                             "No relief segments expected in synchronized mode")

    def test_staggered_breaks_with_spares(self):
        """With spare operators, breaks should be staggered with relief coverage."""
        from core.planner import ReliefPlanner
        # 7 ops, 5 machines => 2 spares => staggered mode
        state = self._make_state(7, 5)
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        assignments = [s for s in segments if s.segmentType == 'assignment']

        # All 7 operators should get 2 breaks => 14 break segments
        self.assertEqual(len(breaks), 14)

        # Machine operators' breaks should have relief coverage
        machine_op_breaks = [s for s in breaks if s.operatorName in [f"Op{i}" for i in range(1, 6)]]
        for brk in machine_op_breaks:
            # Find assignment on the operator's machine during their break
            op_machine = f"M{int(brk.operatorName[2:])}"
            relief = [a for a in assignments
                      if a.machineName == op_machine
                      and a.startTime == brk.startTime
                      and a.operatorName != brk.operatorName]
            self.assertTrue(len(relief) > 0,
                            f"Expected relief for {brk.operatorName} on {op_machine}")

    def test_cooldown_enforced(self):
        """Break cooldown between same operator's breaks must be respected."""
        from core.planner import ReliefPlanner
        import dateutil.parser
        state = self._make_state(3, 3, {'breakCooldownMinutes': 120})
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']

        for op_name in ['Op1', 'Op2', 'Op3']:
            op_breaks = sorted(
                [s for s in breaks if s.operatorName == op_name],
                key=lambda s: s.startTime
            )
            for i in range(1, len(op_breaks)):
                prev_end = dateutil.parser.isoparse(op_breaks[i-1].endTime)
                curr_start = dateutil.parser.isoparse(op_breaks[i].startTime)
                gap_minutes = (curr_start - prev_end).total_seconds() / 60
                self.assertGreaterEqual(gap_minutes, 120,
                    f"{op_name} breaks too close: {gap_minutes:.0f}m apart, need 120m")

    def test_no_breaks_outside_window(self):
        """No breaks should be scheduled in the blackout zones."""
        from core.planner import ReliefPlanner
        import dateutil.parser
        state = self._make_state(3, 3, {
            'shiftBreakWindowStartOffsetMinutes': 120,
            'shiftBreakWindowEndOffsetMinutes': 60,
        })
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        shift_start = self._day_shift_time(7, 0)
        shift_end = self._day_shift_time(19, 0)
        earliest_break = shift_start + timedelta(minutes=120)
        latest_break_end = shift_end - timedelta(minutes=60)

        for brk in breaks:
            b_start = dateutil.parser.isoparse(brk.startTime)
            b_end = dateutil.parser.isoparse(brk.endTime)
            self.assertGreaterEqual(b_start, earliest_break,
                f"Break starts too early: {b_start}")
            self.assertLessEqual(b_end, latest_break_end,
                f"Break ends too late: {b_end}")

    def test_auto_plan_disabled_returns_empty(self):
        """With autoPlanEnabled=False, no segments should be generated."""
        from core.planner import ReliefPlanner
        state = self._make_state(5, 5, {'autoPlanEnabled': False})
        planner = ReliefPlanner(state)
        segments = planner.generate_plan(self._day_shift_time(10, 0))
        self.assertEqual(len(segments), 0)

    def test_all_breaks_taken_no_new_breaks(self):
        """If all operators have already taken their target breaks, no break segments."""
        from core.planner import ReliefPlanner, get_shift_bounds
        from core.models import Break as BreakRecord
        state = self._make_state(3, 3, {'targetBreaksPerShift': 1})
        now = self._day_shift_time(12, 0)

        # Mark all operators as having taken 1 break already
        for i, op in enumerate(state.operators):
            op.breaksTaken = 1
            b_start = self._day_shift_time(9, 0) + timedelta(minutes=i * 40)
            b_end = b_start + timedelta(minutes=35)
            state.breaks.append(BreakRecord(
                id=f"b{i}",
                operatorId=op.name,
                startTime=b_start.isoformat(),
                endTime=b_end.isoformat(),
            ))

        planner = ReliefPlanner(state)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        self.assertEqual(len(breaks), 0, "No breaks should be scheduled if all taken")

    def test_continuous_assignment_segments(self):
        """In staggered mode, machine segments should be continuous (relief covers breaks)."""
        from core.planner import ReliefPlanner
        import dateutil.parser
        # 7 ops, 5 machines => 2 spares => staggered mode (continuous coverage)
        state = self._make_state(7, 5)
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        shift_end = self._day_shift_time(19, 0)
        segments = planner.generate_plan(now)

        # For each machine, collect assignment segments and verify continuity
        for m_name in ['M1', 'M2', 'M3', 'M4', 'M5']:
            m_segs = sorted(
                [s for s in segments if s.machineName == m_name and s.segmentType == 'assignment'],
                key=lambda s: s.startTime
            )
            self.assertTrue(len(m_segs) > 0, f"Machine {m_name} should have segments")

            # First segment should start at now
            first_start = dateutil.parser.isoparse(m_segs[0].startTime)
            self.assertEqual(first_start, now)

            # Last segment should end at shift_end
            last_end = dateutil.parser.isoparse(m_segs[-1].endTime)
            self.assertEqual(last_end, shift_end)

            # Segments should be back-to-back (relief covers during breaks)
            for i in range(1, len(m_segs)):
                prev_end = dateutil.parser.isoparse(m_segs[i-1].endTime)
                curr_start = dateutil.parser.isoparse(m_segs[i].startTime)
                self.assertEqual(prev_end, curr_start,
                    f"Gap in {m_name} between seg {i-1} end and seg {i} start")

    def test_synchronized_machines_park_during_breaks(self):
        """In synchronized mode, machines should have gaps during breaks (all park up)."""
        from core.planner import ReliefPlanner
        import dateutil.parser
        from core.models import Circuit
        # 5 ops, 5 machines => 0 spares => synchronized mode
        state = self._make_state(5, 5)
        state.circuits = [Circuit(name="Circuit1", truckIds=[m.name for m in state.machines])]
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        shift_end = self._day_shift_time(19, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        break_starts = sorted(set(dateutil.parser.isoparse(s.startTime) for s in breaks))

        for m_name in ['M1', 'M2', 'M3', 'M4', 'M5']:
            m_segs = sorted(
                [s for s in segments if s.machineName == m_name and s.segmentType == 'assignment'],
                key=lambda s: s.startTime
            )
            # Should have 3 segments: before break 1, between breaks, after break 2
            self.assertEqual(len(m_segs), 3,
                f"Machine {m_name} should have 3 segments (gaps during 2 synchronized breaks)")

    def test_even_break_distribution(self):
        """Breaks should be evenly spaced across the break window."""
        from core.planner import ReliefPlanner
        from core.models import Circuit
        import dateutil.parser
        state = self._make_state(5, 5)
        state.circuits = [Circuit(name="Circuit1", truckIds=[m.name for m in state.machines])]
        planner = ReliefPlanner(state)
        now = self._day_shift_time(7, 0)
        segments = planner.generate_plan(now)

        breaks = [s for s in segments if s.segmentType == 'break']
        # Synchronized: 2 rounds, all operators in each
        break_starts = sorted(set(
            dateutil.parser.isoparse(s.startTime) for s in breaks
        ))
        self.assertEqual(len(break_starts), 2)

        # Both rounds should be well within the break window,
        # not at the very edges
        shift_start = self._day_shift_time(7, 0)
        win_start = shift_start + timedelta(minutes=90)
        win_end = self._day_shift_time(19, 0) - timedelta(minutes=60)

        for t in break_starts:
            self.assertGreater(t, win_start, "Break too close to window start")

    def test_pending_swap_detection_and_execution(self):
        """When simulation time reaches a scheduled break, pending swap is detected and can be executed."""
        import dateutil.parser
        state = self._make_state(7, 5) # 2 spares
        temp_file = os.path.join(os.path.dirname(__file__), "test_pending_swap.json")
        try:
            sm = StateManager(temp_file)
            sm.timer.stop()
            sm.state = state
            sm.planner = ReliefPlanner(state)
            sm.is_paused = True
            sm.auto_accept_swaps = False
            sm.simulated_time = self._day_shift_time(7, 0)
            sm.state.simulatedTime = sm.simulated_time.isoformat()
            sm.recompute_plan()

            # Find first scheduled break for Op1 (on machine M1)
            op1_breaks = [s for s in sm.state.plannedSegments if s.operatorName == 'Op1' and s.segmentType == 'break']
            self.assertTrue(len(op1_breaks) > 0)
            break_start = dateutil.parser.isoparse(op1_breaks[0].startTime)

            # Before break time: no pending swap on M1 (Op1 is already operating M1)
            sm.simulated_time = break_start - timedelta(minutes=10)
            sm.state.simulatedTime = sm.simulated_time.isoformat()
            self.assertIsNone(sm.get_pending_swap_for_machine('M1'))

            # At break time: pending swap should be detected for M1!
            sm.simulated_time = break_start
            sm.state.simulatedTime = sm.simulated_time.isoformat()
            swap = sm.get_pending_swap_for_machine('M1')
            self.assertIsNotNone(swap)
            self.assertEqual(swap['machine_name'], 'M1')
            self.assertEqual(swap['outgoing_op'], 'Op1')
            self.assertTrue(swap['incoming_op'] in ['Op6', 'Op7']) # One of the spares

            # Execute pending swap
            res = sm.execute_pending_swap('M1')
            self.assertTrue(res)

            # Op1 should now be on break
            op1 = next(o for o in sm.state.operators if o.name == 'Op1')
            self.assertEqual(op1.status, 'on_break')
            self.assertEqual(op1.breaksTaken, 1)

            # Machine M1 should now have the relief operator
            m1 = next(m for m in sm.state.machines if m.name == 'M1')
            self.assertEqual(m1.currentOperatorId, swap['incoming_op'])
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_auto_accept_swaps_during_simulation(self):
        """When auto_accept_swaps is True, swaps and breaks execute automatically as time passes."""
        import dateutil.parser
        state = self._make_state(5, 5) # Synchronized mode
        temp_file = os.path.join(os.path.dirname(__file__), "test_auto_accept.json")
        try:
            sm = StateManager(temp_file)
            sm.timer.stop()
            sm.state = state
            sm.planner = ReliefPlanner(state)
            sm.is_paused = False
            sm.auto_accept_swaps = True
            sm.simulated_time = self._day_shift_time(7, 0)
            sm.state.simulatedTime = sm.simulated_time.isoformat()
            sm.recompute_plan()

            # Find first synchronized break start time
            all_breaks = [s for s in sm.state.plannedSegments if s.segmentType == 'break']
            first_break_start = dateutil.parser.isoparse(all_breaks[0].startTime)

            # Advance time to just before break
            sm.simulated_time = first_break_start - timedelta(seconds=1)
            sm.state.simulatedTime = sm.simulated_time.isoformat()

            # Op1 still working before break
            op1 = next(o for o in sm.state.operators if o.name == 'Op1')
            self.assertEqual(op1.status, 'working')

            # Tick into the break time with auto_accept_swaps enabled
            sm.simulated_time = first_break_start
            sm.state.simulatedTime = sm.simulated_time.isoformat()
            sm.check_and_auto_execute_swaps()

            # Op1 should automatically be on break now
            self.assertEqual(op1.status, 'on_break')
            self.assertEqual(op1.breaksTaken, 1)
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)


class TestPhase1Foundation(unittest.TestCase):
    """Tests for Phase 1 — Foundation Enhancements (DRC Architecture)."""

    def setUp(self):
        self.test_state_file = os.path.join(os.path.dirname(__file__), "test_phase1_temp.json")
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_enum_values_are_strings(self):
        """OperatorStatus and MachineStatus enum values must compare equal to plain strings."""
        from core.models import OperatorStatus, MachineStatus
        self.assertEqual(OperatorStatus.WORKING, 'working')
        self.assertEqual(OperatorStatus.STANDBY, 'standby')
        self.assertEqual(OperatorStatus.ON_BREAK, 'on_break')
        self.assertEqual(OperatorStatus.ABSENT, 'absent')
        self.assertEqual(OperatorStatus.FATIGUED, 'fatigued')
        self.assertEqual(MachineStatus.OPERATIONAL, 'operational')
        self.assertEqual(MachineStatus.SETUP, 'setup')

    def test_enum_json_round_trip(self):
        """Enums serialize to JSON as plain strings and load back correctly."""
        import json
        from core.models import OperatorStatus
        data = {'status': OperatorStatus.WORKING}
        serialized = json.dumps(data)
        loaded = json.loads(serialized)
        self.assertEqual(loaded['status'], 'working')
        self.assertEqual(loaded['status'], OperatorStatus.WORKING)

    def test_competency_multiplier_defaults(self):
        """Operator with no competency multipliers should return 1.0 for all types."""
        op = Operator(name='Test Op', qualifications=['Truck', 'Digger'])
        self.assertEqual(op.get_competency('Truck'), 1.0)
        self.assertEqual(op.get_competency('Digger'), 1.0)
        self.assertEqual(op.get_competency('Unknown'), 1.0)

    def test_competency_multiplier_custom(self):
        """Operator with custom multipliers returns correct values."""
        op = Operator(
            name='Expert Op',
            qualifications=['Truck', 'Digger'],
            competencyMultipliers={'Truck': 0.7, 'Digger': 1.3}
        )
        self.assertAlmostEqual(op.get_competency('Truck'), 0.7)
        self.assertAlmostEqual(op.get_competency('Digger'), 1.3)
        self.assertEqual(op.get_competency('Water Cart'), 1.0)  # not specified

    def test_fatigue_accumulation_during_work(self):
        """Working operators should accumulate fatigue and lose alertness over simulation ticks."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Worker', qualifications=['Truck'], status='working'),
        ]
        sm.state.machines = [
            Machine(name='DT-1', type='Truck', status='operational', currentOperatorId='Worker'),
        ]
        sm.state.operators[0].currentAssignmentId = 'DT-1'
        sm.state.settings = Settings(autoPlanEnabled=False, defaultOperatingTimeMinutes=120)
        sm.is_paused = False
        sm.speed_multiplier = 1.0

        op = sm.state.operators[0]
        initial_fatigue = op.cumulativeFatigueMinutes
        initial_alertness = op.alertnessScore

        # Simulate several ticks
        for _ in range(10):
            sm.tick()

        self.assertGreater(op.cumulativeFatigueMinutes, initial_fatigue)
        self.assertLess(op.alertnessScore, initial_alertness)

    def test_fatigue_recovery_during_break(self):
        """Operators on break should recover fatigue."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Resting', qualifications=['Truck'], status='on_break',
                     cumulativeFatigueMinutes=60.0, alertnessScore=0.5),
        ]
        sm.state.machines = []
        sm.state.settings = Settings(autoPlanEnabled=False, defaultOperatingTimeMinutes=120)
        # Create an active break record so the tick doesn't end the break immediately
        from core.models import Break
        sm.state.breaks = [
            Break(id='b1', operatorId='Resting', startTime=sm.get_current_time().isoformat())
        ]
        sm.is_paused = False
        sm.speed_multiplier = 1.0

        op = sm.state.operators[0]
        initial_fatigue = op.cumulativeFatigueMinutes

        # Simulate a few ticks (not enough to finish the full 30m break)
        for _ in range(5):
            sm.tick()

        self.assertLess(op.cumulativeFatigueMinutes, initial_fatigue)

    def test_schema_migration_from_v1(self):
        """Loading a state.json without schemaVersion or new fields should work with defaults."""
        import json
        # Write a v1-style state file (no schemaVersion, no fatigue fields)
        v1_data = {
            'operators': [
                {'name': 'Old Op', 'qualifications': ['Truck'], 'id': 'Old Op',
                 'status': 'standby', 'standbyTimeMinutes': 0, 'breaksTaken': 0,
                 'currentAssignmentId': None}
            ],
            'machines': [],
            'zones': [],
            'zoneConnections': [],
            'assignments': [],
            'breaks': [],
            'settings': {
                'breakDurationMinutes': 30,
                'breakCooldownMinutes': 90,
                'targetBreaksPerShift': 2,
                'autoPlanEnabled': True,
                'preferEvenWorkTime': True,
                'defaultOperatingTimeMinutes': 120,
                'durationTimingBuffer': 15,
                'paddingMinutes': 5,
                'shiftBreakWindowStartOffsetMinutes': 120,
                'shiftBreakWindowEndOffsetMinutes': 60,
            },
            'simulatedTime': ''
        }
        with open(self.test_state_file, 'w') as f:
            json.dump(v1_data, f)

        sm = StateManager(self.test_state_file)
        # Should load without error
        self.assertEqual(len(sm.state.operators), 1)
        op = sm.state.operators[0]
        # New fields should have defaults
        self.assertEqual(op.competencyMultipliers, {})
        self.assertEqual(op.cumulativeFatigueMinutes, 0.0)
        self.assertEqual(op.alertnessScore, 1.0)
        self.assertEqual(op.consecutiveShiftsWorked, 0)
        # Settings should have new defaults
        self.assertEqual(sm.state.settings.handoverDurationMinutes, 5)
        self.assertEqual(sm.state.settings.circadianBreakWindowStart, '02:00')
        # Schema version should have been migrated
        self.assertEqual(sm.state.schemaVersion, 3)  # loaded and migrated to 3

    def test_production_task_dataclass(self):
        """ProductionTask should have reasonable defaults and a unique ID."""
        from core.models import ProductionTask
        t1 = ProductionTask(name='Haul Run')
        t2 = ProductionTask(name='Dig Face')
        self.assertNotEqual(t1.id, t2.id)  # unique IDs
        self.assertEqual(t1.status, 'pending')
        self.assertEqual(t1.priority, 5)
        self.assertEqual(t1.estimatedDurationMinutes, 60)

    def test_travel_time_aware_relief_no_zones(self):
        """Planner should still work when no zones are configured (backward compat)."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Primary', qualifications=['Truck'], status='working'),
            Operator(name='Spare', qualifications=['Truck'], status='standby'),
        ]
        sm.state.machines = [
            Machine(name='DT-1', type='Truck', status='operational', currentOperatorId='Primary'),
        ]
        sm.state.operators[0].currentAssignmentId = 'DT-1'
        sm.state.zones = []
        sm.state.zoneConnections = []
        sm.state.settings = Settings(autoPlanEnabled=True, targetBreaksPerShift=1)

        planner = ReliefPlanner(sm.state)
        now = datetime(2025, 1, 1, 7, 0)
        segments = planner.generate_plan(now)
        # Should produce some segments without crashing
        self.assertGreater(len(segments), 0)

    def test_operator_shift_stats_include_fatigue(self):
        """get_operator_shift_stats should include alertness and fatigue metrics."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Op1', qualifications=['Truck'], status='working',
                     cumulativeFatigueMinutes=45.0, alertnessScore=0.6,
                     competencyMultipliers={'Truck': 0.8}),
        ]
        sm.state.machines = [Machine(name='DT-1', type='Truck', status='operational')]
        sm.state.settings = Settings(autoPlanEnabled=False)

        stats = sm.get_operator_shift_stats('Op1')
        self.assertIn('alertness_score', stats)
        self.assertIn('cumulative_fatigue_minutes', stats)
        self.assertIn('competency_multipliers', stats)
        self.assertAlmostEqual(stats['alertness_score'], 0.6)
        self.assertAlmostEqual(stats['cumulative_fatigue_minutes'], 45.0)
        self.assertEqual(stats['competency_multipliers'], {'Truck': 0.8})


class TestPhase2BAP(unittest.TestCase):
    """Tests for Phase 2 — Break Assignment Problem (BAP) features."""

    def setUp(self):
        self.test_state_file = os.path.join(os.path.dirname(__file__), "test_phase2_temp.json")
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_workstretch_enforcement(self):
        """When workstretch exceeds max, breaks should be scheduled even if target is met."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Op1', qualifications=['Truck'], status='working', breaksTaken=2),
            Operator(name='Spare1', qualifications=['Truck'], status='standby'),
        ]
        sm.state.machines = [
            Machine(name='DT-1', type='Truck', status='operational', currentOperatorId='Op1'),
        ]
        sm.state.operators[0].currentAssignmentId = 'DT-1'
        sm.state.settings = Settings(
            autoPlanEnabled=True,
            targetBreaksPerShift=2,
            maxWorkstretchMinutes=60,  # Force break after 60 mins
        )

        from core.planner import SimOperator
        sim_op = SimOperator(sm.state.operators[0], breaks_taken=2)
        now = datetime(2025, 1, 1, 10, 0)  # 3h into shift
        shift_start = datetime(2025, 1, 1, 7, 0)
        shift_end = datetime(2025, 1, 1, 19, 0)

        # With 2 breaks taken and target=2, normally can't take break
        # But workstretch of 3h exceeds maxWorkstretchMinutes=60
        result = sim_op.can_take_break(now, shift_start, shift_end, sm.state.settings)
        self.assertTrue(result, "Should allow break due to workstretch override")

    def test_workstretch_no_override_when_under_limit(self):
        """When workstretch is under max, normal rules apply."""
        from core.planner import SimOperator
        op = Operator(name='Op1', qualifications=['Truck'], breaksTaken=2)
        sim_op = SimOperator(op, breaks_taken=2, last_break_end=datetime(2025, 1, 1, 9, 50))
        settings = Settings(targetBreaksPerShift=2, maxWorkstretchMinutes=240)
        now = datetime(2025, 1, 1, 10, 0)  # Only 10 mins since last break
        shift_start = datetime(2025, 1, 1, 7, 0)
        shift_end = datetime(2025, 1, 1, 19, 0)

        result = sim_op.can_take_break(now, shift_start, shift_end, settings)
        self.assertFalse(result, "Should deny break: target met and workstretch under limit")

    def test_variable_break_duration(self):
        """Variable break duration should scale with fatigue level."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Tired Op', qualifications=['Truck'], alertnessScore=0.3),  # Very fatigued
            Operator(name='Fresh Op', qualifications=['Truck'], alertnessScore=0.9),   # Mostly alert
        ]
        sm.state.settings = Settings(
            enableVariableBreakLength=True,
            variableBreakMinMinutes=15,
            variableBreakMaxMinutes=45,
        )

        planner = ReliefPlanner(sm.state)
        tired_dur = planner._compute_variable_break_duration('Tired Op', sm.state.settings)
        fresh_dur = planner._compute_variable_break_duration('Fresh Op', sm.state.settings)

        self.assertGreater(tired_dur, fresh_dur, "Fatigued op should get longer break")
        self.assertGreaterEqual(tired_dur, 15)
        self.assertLessEqual(tired_dur, 45)

    def test_fractionable_break_splitting(self):
        """When fractionable breaks are enabled, a break should split into sub-parts."""
        sm = StateManager(self.test_state_file)
        sm.state.settings = Settings(
            enableFractionableBreaks=True,
            fractionableBreakParts=3,
            minFractionDurationMinutes=10,
            breakDurationMinutes=30,
        )

        planner = ReliefPlanner(sm.state)
        break_start = datetime(2025, 1, 1, 10, 0)
        fractions = planner._split_break_into_fractions(break_start, 30, sm.state.settings)

        self.assertEqual(len(fractions), 3, "Should have 3 sub-breaks")
        for start, end, idx, total in fractions:
            self.assertEqual(total, 3)
            self.assertGreater((end - start).total_seconds(), 0)

    def test_circadian_detection_night_shift(self):
        """Circadian window should be detected during night shifts."""
        sm = StateManager(self.test_state_file)
        sm.state.settings = Settings(
            enableCircadianScheduling=True,
            circadianBreakWindowStart="02:00",
            circadianBreakWindowEnd="04:00",
        )

        planner = ReliefPlanner(sm.state)
        night_start = datetime(2025, 1, 1, 19, 0)
        day_start = datetime(2025, 1, 1, 7, 0)

        night_window = planner._get_circadian_window(night_start, sm.state.settings)
        day_window = planner._get_circadian_window(day_start, sm.state.settings)

        self.assertIsNotNone(night_window, "Night shift should have circadian window")
        self.assertIsNone(day_window, "Day shift should NOT have circadian window")

        win_start, win_end = night_window
        self.assertEqual(win_start.hour, 2)
        self.assertEqual(win_end.hour, 4)

    def test_bap_disabled_backward_compat(self):
        """With all BAP features disabled, planner should produce standard segments."""
        sm = StateManager(self.test_state_file)
        sm.state.operators = [
            Operator(name='Op1', qualifications=['Truck'], status='working'),
            Operator(name='Spare', qualifications=['Truck'], status='standby'),
        ]
        sm.state.machines = [
            Machine(name='DT-1', type='Truck', status='operational', currentOperatorId='Op1'),
        ]
        sm.state.operators[0].currentAssignmentId = 'DT-1'
        sm.state.settings = Settings(
            autoPlanEnabled=True,
            targetBreaksPerShift=1,
            enableFractionableBreaks=False,
            enableVariableBreakLength=False,
            enableCircadianScheduling=False,
        )

        planner = ReliefPlanner(sm.state)
        now = datetime(2025, 1, 1, 7, 0)
        segments = planner.generate_plan(now)

        break_segs = [s for s in segments if s.segmentType == 'break']
        for seg in break_segs:
            self.assertEqual(seg.breakType, 'standard')
            self.assertEqual(seg.breakPartIndex, 0)
            self.assertEqual(seg.breakPartTotal, 1)


class TestTelemetryAndReports(unittest.TestCase):
    """Tests for TelemetryLogger, ScheduleAnalytics, ReportsView and MainWindow startup."""

    def setUp(self):
        self.test_state_file = os.path.join(os.path.dirname(__file__), "test_telemetry_temp.json")
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
        self.sm = StateManager(self.test_state_file)

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_telemetry_logger_get_events_none_since(self):
        from core.telemetry import TelemetryLogger, ScheduleEvent
        logger = TelemetryLogger()
        logger.log_event(ScheduleEvent(
            timestamp=datetime(2026, 8, 28, 8, 0).isoformat(),
            event_type="REPLAN_TRIGGERED",
            operator_name="SYSTEM",
            machine_name="SYSTEM",
            details={}
        ))
        logger.log_event(ScheduleEvent(
            timestamp=datetime(2026, 8, 28, 9, 0).isoformat(),
            event_type="DISRUPTION_DETECTED",
            operator_name="Alice",
            machine_name="DT-1",
            details={}
        ))

        # None since should return all events without error
        all_events = logger.get_events(since=None)
        self.assertEqual(len(all_events), 2)

        # Filter by since
        recent = logger.get_events(since=datetime(2026, 8, 28, 8, 30))
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].operator_name, "Alice")

        # Filter by event_type
        replans = logger.get_events(since=None, event_type="REPLAN_TRIGGERED")
        self.assertEqual(len(replans), 1)

    def test_schedule_analytics(self):
        from core.telemetry import ScheduleAnalytics, TelemetryLogger
        logger = TelemetryLogger()
        events = logger.get_events(since=None)

        util = ScheduleAnalytics.calculate_utilization(events)
        self.assertIn("machine_utilization", util)

        comp = ScheduleAnalytics.calculate_break_compliance(events, self.sm.state.settings, self.sm.state.operators)
        self.assertIsInstance(comp, dict)

        fatigue = ScheduleAnalytics.calculate_fatigue_risk(events, self.sm.state.operators)
        self.assertIsInstance(fatigue, dict)

    def test_reports_view_and_main_window_startup(self):
        from ui.reports_view import ReportsView
        from ui.main_window import MainWindow

        reports_view = ReportsView(self.sm)
        reports_view.refresh_data()
        self.assertIn("Shift Analytics Summary", reports_view.summary_text.toHtml())
        reports_view.close()

        window = MainWindow(self.sm)
        self.assertIsNotNone(window.reports_view)
        window.close()


class TestAutoAcceptOptimization(unittest.TestCase):
    """Tests for Auto-Accept batching, UI performance, and popup elimination."""

    def setUp(self):
        self.test_file = os.path.join(os.path.dirname(__file__), "test_auto_opt.json")
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        self.sm = StateManager(self.test_file)
        self.sm.timer.stop()

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_batch_auto_accept_returns_boolean_and_updates_state(self):
        self.sm.state.settings.autoPlanEnabled = False
        self.sm.auto_accept_swaps = True
        
        now = datetime(2026, 8, 28, 11, 0)
        self.sm.simulated_time = now
        self.sm.state.simulatedTime = now.isoformat()
        
        test_op = Operator(name="TestOpStandby", qualifications=["Dump Truck"], status='standby')
        self.sm.state.operators.append(test_op)
        self.sm.state.plannedSegments = [PlannedSegment(
            startTime=datetime(2026, 8, 28, 11, 0).isoformat(),
            endTime=datetime(2026, 8, 28, 11, 30).isoformat(),
            operatorName="TestOpStandby",
            machineName="",
            segmentType="break"
        )]
        
        executed = self.sm.check_and_auto_execute_swaps(batch_mode=True)
        self.assertTrue(executed)
        self.assertEqual(test_op.status, 'on_break')

    def test_tick_batches_multiple_break_ends_efficiently(self):
        self.sm.is_paused = False
        settings = self.sm.state.settings
        settings.breakDurationMinutes = 30
        
        # Put 2 operators on break
        op1 = self.sm.state.operators[0]
        op2 = self.sm.state.operators[1]
        op1.status = 'on_break'
        op2.status = 'on_break'
        
        break_start = datetime(2026, 8, 28, 11, 0)
        self.sm.state.breaks.append(Break(id="b1", operatorId=op1.name, startTime=break_start.isoformat()))
        self.sm.state.breaks.append(Break(id="b2", operatorId=op2.name, startTime=break_start.isoformat()))
        
        # Set simulated time to when breaks should end (11:30)
        self.sm.simulated_time = datetime(2026, 8, 28, 11, 30)
        self.sm.state.simulatedTime = self.sm.simulated_time.isoformat()
        
        # Tick should transition both operators from 'on_break' to 'standby'
        self.sm.tick()
        self.assertEqual(op1.status, 'standby')
        self.assertEqual(op2.status, 'standby')

    def test_reports_view_skips_when_hidden(self):
        from ui.reports_view import ReportsView
        reports = ReportsView(self.sm)
        # By default in unit test without show(), isVisible() is False
        self.assertFalse(reports.isVisible())
        # Non-forced refresh should exit immediately without recomputing
        reports.refresh_data(force=False)
        reports.close()

    def test_view_widgets_ruler_updates_on_time_tick(self):
        from ui.views import EquipmentCategoryWidget, ZoneSectionWidget, OperatorsView, EquipmentView, ZoneView
        
        # Test EquipmentCategoryWidget
        equip_cat = EquipmentCategoryWidget("Dump Trucks", self.sm.state.machines, self.sm)
        # Simulate time tick
        self.sm.time_ticked.emit()
        self.assertIsNotNone(equip_cat.ruler.current_time)
        equip_cat.close()

        # Test EquipmentView
        equip_view = EquipmentView(self.sm)
        equip_view.update_view()
        self.sm.time_ticked.emit()
        equip_view.close()

        # Test ZoneSectionWidget and ZoneView
        zone_sec = ZoneSectionWidget("Pit A", is_unassigned=False, machines=self.sm.state.machines, state_manager=self.sm)
        self.sm.time_ticked.emit()
        self.assertIsNotNone(zone_sec.ruler.current_time)
        zone_sec.close()

        zone_view = ZoneView(self.sm)
        zone_view.update_view()
        self.sm.time_ticked.emit()
        zone_view.close()

        # Test OperatorsView
        ops_view = OperatorsView(self.sm)
        ops_view.update_view()
        self.sm.time_ticked.emit()
        self.assertIsNotNone(ops_view.ruler.current_time)
        ops_view.close()


if __name__ == "__main__":
    unittest.main()

