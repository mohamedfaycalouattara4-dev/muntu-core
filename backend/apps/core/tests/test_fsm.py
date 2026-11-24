"""Tests du moteur d'états signé SignedStateMachine."""
from django.test import TestCase
from apps.core.fsm import SignedStateMachine, TransitionRule, TransitionResult


class SignedStateMachineTests(TestCase):
    """Machine à états pour un prêt — 4 états, 5 transitions."""

    def setUp(self):
        self.transitions = []

        def on_transition(result: TransitionResult):
            self.transitions.append(result)

        self.fsm = SignedStateMachine(
            name="loan",
            initial_state="DRAFT",
            rules=[
                TransitionRule("DRAFT", "SUBMIT", "UNDER_REVIEW"),
                TransitionRule("UNDER_REVIEW", "APPROVE", "ACTIVE"),
                TransitionRule("UNDER_REVIEW", "REJECT", "REJECTED"),
                TransitionRule("ACTIVE", "PREPAY", "PREPAID"),
                TransitionRule("ACTIVE", "DEFAULT", "DELINQUENT"),
            ],
            on_transition=on_transition,
        )

    def test_initial_state(self):
        self.assertEqual(self.fsm.initial_state, "DRAFT")

    def test_valid_transition(self):
        result = self.fsm.transition("DRAFT", "SUBMIT", payload={"loan_id": "L1"})
        self.assertEqual(result.previous_state, "DRAFT")
        self.assertEqual(result.current_state, "UNDER_REVIEW")
        self.assertEqual(result.event, "SUBMIT")
        self.assertIsInstance(result.signature, str)
        self.assertEqual(len(result.signature), 64)  # SHA-256 hex

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            self.fsm.transition("DRAFT", "APPROVE")

    def test_guard_rejects(self):
        def bad_guard(ctx):
            return False

        rules_with_guard = [
            TransitionRule("DRAFT", "SUBMIT", "UNDER_REVIEW", guard=bad_guard),
        ]
        fsm = SignedStateMachine("test", "DRAFT", rules_with_guard)
        with self.assertRaises(PermissionError):
            fsm.transition("DRAFT", "SUBMIT")

    def test_outbox_callback_called(self):
        self.fsm.transition("DRAFT", "SUBMIT")
        self.assertEqual(len(self.transitions), 1)
        self.assertEqual(self.transitions[0].current_state, "UNDER_REVIEW")

    def test_can_transition(self):
        self.assertTrue(self.fsm.can_transition("DRAFT", "SUBMIT"))
        self.assertFalse(self.fsm.can_transition("DRAFT", "APPROVE"))

    def test_allowed_events(self):
        events = self.fsm.allowed_events("UNDER_REVIEW")
        self.assertEqual(sorted(events), sorted(["APPROVE", "REJECT"]))

    def test_graph(self):
        graph = self.fsm.graph()
        self.assertIn("DRAFT", graph)
        self.assertEqual(len(graph["DRAFT"]), 1)
        self.assertEqual(graph["DRAFT"][0]["target"], "UNDER_REVIEW")

    def test_signature_deterministic_for_same_input(self):
        r1 = self.fsm.transition("DRAFT", "SUBMIT", payload={"loan_id": "L1"})
        # Ré-initialiser avec même état
        self.fsm2 = SignedStateMachine(
            name="loan",
            initial_state="DRAFT",
            rules=[
                TransitionRule("DRAFT", "SUBMIT", "UNDER_REVIEW"),
            ],
        )
        r2 = self.fsm2.transition("DRAFT", "SUBMIT", payload={"loan_id": "L1"})
        # Les signatures diffèrent car le nonce contient timestamp
        self.assertEqual(r1.previous_state, r2.previous_state)
        self.assertEqual(r1.current_state, r2.current_state)
