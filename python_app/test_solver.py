import unittest
from datetime import datetime
import os

from core.models import AppState, Settings, Operator, Machine
from core.solver import SolverPlanner

class TestSolverPlanner(unittest.TestCase):
    def setUp(self):
        self.state = AppState(
            operators=[
                Operator(name="Op1", qualifications=["Truck"], status="working"),
                Operator(name="Op2", qualifications=["Truck"], status="standby")
            ],
            machines=[
                Machine(name="DT-1", type="Truck", status="operational", currentOperatorId="Op1")
            ],
            settings=Settings(autoPlanEnabled=True, targetBreaksPerShift=1)
        )
        self.state.operators[0].currentAssignmentId = "DT-1"

    def test_solver_fallback(self):
        """Test that the solver falls back to heuristic planner without crashing."""
        planner = SolverPlanner(self.state)
        now = datetime(2025, 1, 1, 7, 0)
        
        segments = planner.generate_plan(now)
        # Should generate some segments via the fallback planner
        self.assertGreater(len(segments), 0)
        self.assertTrue(any(s.segmentType == "break" for s in segments))

if __name__ == "__main__":
    unittest.main()
