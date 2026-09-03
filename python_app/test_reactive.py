import unittest
from datetime import datetime
import os

from core.models import AppState, Settings, Operator, Machine
from core.reactive_engine import ReactiveEngine

class TestReactiveEngine(unittest.TestCase):
    def setUp(self):
        self.state = AppState(
            operators=[
                Operator(name="Op1", qualifications=["Truck"], status="working", alertnessScore=1.0),
                Operator(name="Op2", qualifications=["Truck"], status="standby", alertnessScore=1.0)
            ],
            machines=[
                Machine(name="DT-1", type="Truck", status="operational", currentOperatorId="Op1"),
                Machine(name="DT-2", type="Truck", status="operational", currentOperatorId=None)
            ],
            settings=Settings(autoPlanEnabled=True, targetBreaksPerShift=1)
        )
        self.state.operators[0].currentAssignmentId = "DT-1"
        self.engine = ReactiveEngine()

    def test_no_disruptions(self):
        now = datetime(2025, 1, 1, 7, 0)
        disruptions = self.engine.detect_disruptions(self.state, now)
        self.assertEqual(len(disruptions), 0)
        self.assertFalse(self.engine.should_replan(disruptions))

    def test_machine_down_disruption(self):
        now = datetime(2025, 1, 1, 8, 0)
        self.state.machines[0].status = 'maintenance'
        disruptions = self.engine.detect_disruptions(self.state, now)
        self.assertEqual(len(disruptions), 1)
        self.assertEqual(disruptions[0].type, 'machine_down')
        self.assertTrue(self.engine.should_replan(disruptions))

    def test_operator_absent_disruption(self):
        now = datetime(2025, 1, 1, 9, 0)
        self.state.operators[0].status = 'absent'
        disruptions = self.engine.detect_disruptions(self.state, now)
        self.assertEqual(len(disruptions), 1)
        self.assertEqual(disruptions[0].type, 'operator_absent')
        self.assertTrue(self.engine.should_replan(disruptions))

    def test_fatigue_alert_disruption(self):
        now = datetime(2025, 1, 1, 10, 0)
        # Below warning threshold (0.4) but above critical (0.2)
        self.state.operators[0].alertnessScore = 0.3
        disruptions = self.engine.detect_disruptions(self.state, now)
        self.assertEqual(len(disruptions), 1)
        self.assertEqual(disruptions[0].type, 'fatigue_alert')
        self.assertEqual(disruptions[0].severity, 'medium')
        # Medium severity shouldn't force a full replan alone, but it gets logged
        self.assertFalse(self.engine.should_replan(disruptions))

        # Drop below critical (0.2)
        self.state.operators[0].alertnessScore = 0.1
        disruptions = self.engine.detect_disruptions(self.state, now)
        self.assertEqual(disruptions[0].severity, 'critical')
        self.assertTrue(self.engine.should_replan(disruptions))


if __name__ == "__main__":
    unittest.main()
