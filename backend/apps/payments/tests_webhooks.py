from django.test import TestCase
from unittest.mock import MagicMock

from .services.circuit_breaker import CircuitOpenError
from .services.signature import compute_raw_signature


class CircuitBreakerTests(TestCase):
    def test_opens_after_5_failures(self):
        from .services.circuit_breaker import call
        fn = MagicMock(side_effect=RuntimeError("boom"))
        from django.core.cache import cache
        cache.clear()
        for _ in range(5):
            with self.assertRaises(RuntimeError):
                call("WAVE", fn)
        with self.assertRaises(CircuitOpenError):
            call("WAVE", fn)

    def test_signature_roundtrip(self):
        body = b'{"tenant_id":"T1","amount_xof":1000}'
        sig = compute_raw_signature(body, None)
        from .services.signature import verify_aggregator_signature
        self.assertTrue(verify_aggregator_signature(body, sig))
        self.assertFalse(verify_aggregator_signature(body, "tampered"))
