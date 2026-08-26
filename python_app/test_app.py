import os
import sys
import unittest
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from core.models import Operator, Machine, Zone, Settings
from core.planner import ReliefPlanner
from core.state_manager import StateManager, format_operator_short_name
from ui.timeline_widget import TimelineRulerWidget, TimelineTrackWidget
from ui.views import MachineRowWidget, OperatorRowWidget, ZoneView, EquipmentView, OperatorsView
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
        """With 0 spare operators, all operators should break at the same time."""
        from core.planner import ReliefPlanner
        # 5 ops, 5 machines => 0 spares => synchronized mode
        state = self._make_state(5, 5)
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
        # 5 ops, 5 machines => 0 spares => synchronized mode
        state = self._make_state(5, 5)
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
        import dateutil.parser
        state = self._make_state(5, 5)
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


if __name__ == "__main__":
    unittest.main()
