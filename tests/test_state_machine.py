"""
状态机单元测试
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.state_machine import StateMachine, AgentState


class TestStateMachine(unittest.TestCase):

    def setUp(self):
        self.sm = StateMachine("Test")
        self.sm.transition(AgentState.IDLE)

    def test_initial_state(self):
        sm = StateMachine("Test2")
        self.assertEqual(sm.state, AgentState.STARTING)

    def test_valid_transition(self):
        self.assertTrue(self.sm.transition(AgentState.CONNECTING))
        self.assertEqual(self.sm.state, AgentState.CONNECTING)

    def test_invalid_transition(self):
        self.assertFalse(self.sm.transition(AgentState.HOSTING))
        self.assertEqual(self.sm.state, AgentState.IDLE)

    def test_full_lifecycle(self):
        self.assertTrue(self.sm.transition(AgentState.CONNECTING))
        self.assertTrue(self.sm.transition(AgentState.CONNECTED))
        self.assertTrue(self.sm.transition(AgentState.HOSTING))
        self.assertTrue(self.sm.transition(AgentState.CONNECTED))
        self.assertTrue(self.sm.transition(AgentState.SUSPENDED))
        self.assertTrue(self.sm.transition(AgentState.IDLE))
        self.assertTrue(self.sm.transition(AgentState.EXITING))

    def test_forced_transition(self):
        self.assertTrue(self.sm.transition(AgentState.CONNECTING))
        self.assertTrue(self.sm.transition(AgentState.CONNECTED))
        # 强制从 CONNECTED 到 IDLE（跳过合法路径）
        self.sm.force_transition(AgentState.IDLE)
        self.assertEqual(self.sm.state, AgentState.IDLE)

    def test_is_controlling(self):
        self.assertFalse(self.sm.is_controlling)
        self.sm.transition(AgentState.CONNECTING)
        self.sm.transition(AgentState.CONNECTED)
        self.sm.transition(AgentState.HOSTING)
        self.assertTrue(self.sm.is_controlling)

    def test_time_in_state(self):
        import time
        time.sleep(0.1)
        self.assertGreater(self.sm.time_in_state(), 0.05)

    def test_observer_callback(self):
        transitions = []
        self.sm.add_observer(lambda old, new: transitions.append((old, new)))
        self.sm.transition(AgentState.CONNECTING)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0], (AgentState.IDLE, AgentState.CONNECTING))


if __name__ == "__main__":
    unittest.main()
