import os
import sys
import unittest
from datetime import datetime

from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from core.models import AppState, Operator, Machine, Zone, Settings
from core.state_manager import StateManager
from core.planner import ReliefPlanner
from ui.allocation_wizard import (
    AllocationWizardDialog, is_digger, is_rom_loader, is_truck, is_auxiliary
)

class TestDailyAllocationWizard(unittest.TestCase):
    def setUp(self):
        self.test_state_file = os.path.join(os.path.dirname(__file__), "test_wizard_temp.json")
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)
            
        self.sm = StateManager(self.test_state_file)
        
        self.sm.state.operators = [
            Operator(name="Alice Smith", qualifications=["Truck", "Water Cart"]),
            Operator(name="Bob Jones", qualifications=["Digger", "ROM Loader"]),
            Operator(name="Charlie Davis", qualifications=["Truck", "Digger"]),
            Operator(name="Diana Prince", qualifications=["Truck"]),
            Operator(name="Evan Wright", qualifications=["Truck"]),
            Operator(name="Frank Miller", qualifications=["Water Cart", "Dozer"]),
            Operator(name="Grace Hopper", qualifications=["Truck"]),
        ]
        self.sm.state.machines = [
            Machine(name="EX-101", type="Digger", zoneId="North Pit"),
            Machine(name="EX-102", type="Digger", zoneId="North Pit"),
            Machine(name="LD-201", type="ROM Loader", zoneId="ROM Pad"),
            Machine(name="DZ-301", type="Dozer", zoneId="South Pit"),
            Machine(name="DT-401", type="Truck", zoneId="North Pit"),
            Machine(name="DT-402", type="Truck", zoneId="North Pit"),
            Machine(name="DT-403", type="Truck", zoneId="North Pit"),
        ]
        self.sm.state.zones = [Zone(name="North Pit"), Zone(name="South Pit"), Zone(name="ROM Pad")]
        self.sm.state.settings = Settings(autoPlanEnabled=True)
        self.sm.reset_to_start_of_shift()

    def tearDown(self):
        if os.path.exists(self.test_state_file):
            os.remove(self.test_state_file)

    def test_category_filters(self):
        self.assertTrue(is_digger("Digger"))
        self.assertTrue(is_digger("Excavator"))
        self.assertTrue(is_rom_loader("ROM Loader"))
        self.assertTrue(is_truck("Truck"))
        self.assertTrue(is_truck("Haul Truck"))
        self.assertTrue(is_auxiliary("Dozer"))
        self.assertTrue(is_auxiliary("Grader"))
        self.assertTrue(is_auxiliary("Water Cart"))
        self.assertFalse(is_auxiliary("Digger"))
        self.assertFalse(is_auxiliary("Truck"))

    def test_apply_daily_allocation(self):
        allocations = {
            "EX-101": "Bob Jones",
            "EX-102": None,
            "LD-201": None,
            "DZ-301": "Frank Miller",
            "DT-401": "Alice Smith",
            "DT-402": "Charlie Davis",
            "DT-403": None
        }
        absent_operators = ["Grace Hopper"]
        not_required_machines = ["EX-102"]

        self.sm.apply_daily_allocation(
            allocations=allocations,
            absent_operator_names=absent_operators,
            not_required_machine_names=not_required_machines,
            reset_shift_time=True,
            reset_metrics=True
        )

        grace = next(o for o in self.sm.state.operators if o.name == "Grace Hopper")
        self.assertEqual(grace.status, "absent")
        self.assertIsNone(grace.currentAssignmentId)

        ex102 = next(m for m in self.sm.state.machines if m.name == "EX-102")
        self.assertEqual(ex102.status, "not_required")
        self.assertIsNone(ex102.currentOperatorId)

        bob = next(o for o in self.sm.state.operators if o.name == "Bob Jones")
        self.assertEqual(bob.status, "working")
        self.assertEqual(bob.currentAssignmentId, "EX-101")
        ex101 = next(m for m in self.sm.state.machines if m.name == "EX-101")
        self.assertEqual(ex101.status, "operational")
        self.assertEqual(ex101.currentOperatorId, "Bob Jones")

        diana = next(o for o in self.sm.state.operators if o.name == "Diana Prince")
        self.assertEqual(diana.status, "standby")
        self.assertIsNone(diana.currentAssignmentId)

    def test_prevent_duplicate_dropdown_assignments(self):
        dialog = AllocationWizardDialog(self.sm)
        # Step 2: Diggers
        dialog.go_to_step(1)
        diggers_step = dialog.diggers_step
        self.assertEqual(len(diggers_step.row_widgets), 2)
        
        row1 = diggers_step.row_widgets[0] # EX-101
        row2 = diggers_step.row_widgets[1] # EX-102
        
        row1_items = [row1.op_combo.itemData(i) for i in range(row1.op_combo.count())]
        self.assertNotIn("Alice Smith", row1_items)
        self.assertIn("Bob Jones", row1_items)
        self.assertIn("Charlie Davis", row1_items)
        
        # Assign Bob Jones to EX-101
        bob_idx = row1.op_combo.findData("Bob Jones")
        row1.op_combo.setCurrentIndex(bob_idx)
        
        # Check that EX-102's dropdown now does NOT have Bob Jones
        row2_items = [row2.op_combo.itemData(i) for i in range(row2.op_combo.count())]
        self.assertNotIn("Bob Jones", row2_items)
        self.assertIn("Charlie Davis", row2_items)
        
        # Clear EX-101
        row1.clear_assignment()
        
        # Check that EX-102's dropdown now has Bob Jones back
        row2_items_after_clear = [row2.op_combo.itemData(i) for i in range(row2.op_combo.count())]
        self.assertIn("Bob Jones", row2_items_after_clear)
        
        dialog.close()

if __name__ == "__main__":
    unittest.main()
