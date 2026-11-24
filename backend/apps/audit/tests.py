from django.db import ProgrammingError, transaction
from django.test import TestCase

from apps.core.services.audit import emit


class AuditChainTests(TestCase):
    def test_chain_integrity(self):
        emit("order", "o1", "created", {"state": "RESERVATION_STOCK"})
        emit("payment", "p1", "created", {"amount": 1000})
        from apps.audit.models import AuditEvent
        events = list(AuditEvent.objects.order_by("id"))
        self.assertEqual(events[0].previous_hash, "0" * 64)
        self.assertEqual(events[1].previous_hash, events[0].current_hash)

    def test_tampering_is_refused_by_the_database(self):
        """La falsification n'est plus « détectable a posteriori » : elle est impossible.

        Le trigger append-only refuse l'UPDATE au niveau PostgreSQL, y compris
        pour le propriétaire de la table et pour un accès SQL direct.
        """
        emit("order", "o2", "created", {"x": 1})
        from apps.audit.models import AuditEvent

        ev = AuditEvent.objects.first()
        ev.action = "tampered"
        with self.assertRaises(ProgrammingError) as ctx:
            with transaction.atomic():
                ev.save()
        self.assertIn("append-only", str(ctx.exception).lower())

        from apps.audit.services import verify_chain
        self.assertEqual(verify_chain(), 0)
        self.assertEqual(AuditEvent.objects.first().action, "created")

    def test_deletion_is_refused_by_the_database(self):
        emit("order", "o3", "created", {"x": 1})
        from apps.audit.models import AuditEvent

        with self.assertRaises(ProgrammingError):
            with transaction.atomic():
                AuditEvent.objects.filter(entity_id="o3").delete()
        self.assertTrue(AuditEvent.objects.filter(entity_id="o3").exists())
