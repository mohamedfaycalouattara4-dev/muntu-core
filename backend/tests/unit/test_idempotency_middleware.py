"""Middleware idempotency : replay, verrou atomique et anti-race condition."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIClient
from rest_framework.views import APIView

CALLS = {"count": 0}
_lock = threading.Lock()


class EchoView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"echo": request.data.get("x", 1), "ts": "now"})


class SlowView(APIView):
    """Vue lente : simule la fenêtre de course entre deux requêtes jumelles."""
    permission_classes = [AllowAny]

    def post(self, request):
        with _lock:
            CALLS["count"] += 1
        time.sleep(0.4)
        return Response({"processed": True})


class BoomView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raise RuntimeError("boom")


class FailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"detail": "nope"}, status=400)


urlpatterns = [
    path("echo/", EchoView.as_view()),
    path("slow/", SlowView.as_view()),
    path("boom/", BoomView.as_view()),
    path("fail/", FailView.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class IdempotencyMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        CALLS["count"] = 0

    def test_first_request_proceeds(self):
        r = self.client.post("/echo/", {"x": 42}, format="json",
                             HTTP_IDEMPOTENCY_KEY="abc")
        self.assertEqual(r.status_code, 200)

    def test_second_same_key_returns_cached(self):
        from unittest.mock import patch
        with patch.object(EchoView, "post") as mock_post:
            mock_post.return_value = Response({"echo": 42}, status=200)
            self.client.post("/echo/", {"x": 42}, format="json",
                             HTTP_IDEMPOTENCY_KEY="xyz")
            mock_post.assert_called_once()
            r2 = self.client.post("/echo/", {"x": 42}, format="json",
                                  HTTP_IDEMPOTENCY_KEY="xyz")
            self.assertEqual(mock_post.call_count, 1)
            self.assertEqual(r2["Idempotent-Replay"], "true")

    def test_no_key_is_transparent(self):
        r = self.client.post("/echo/", {"x": 1}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Idempotent-Replay", r)

    def test_key_reuse_with_other_payload_is_rejected(self):
        self.client.post("/echo/", {"x": 1}, format="json", HTTP_IDEMPOTENCY_KEY="k1")
        r = self.client.post("/echo/", {"x": 2}, format="json", HTTP_IDEMPOTENCY_KEY="k1")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["code"], "idempotency_key_reuse")

    def test_failed_response_releases_the_lock(self):
        r1 = self.client.post("/fail/", {"x": 1}, format="json", HTTP_IDEMPOTENCY_KEY="k2")
        self.assertEqual(r1.status_code, 400)
        # La clé reste rejouable : la requête est ré-exécutée, pas rejouée.
        r2 = self.client.post("/fail/", {"x": 1}, format="json", HTTP_IDEMPOTENCY_KEY="k2")
        self.assertEqual(r2.status_code, 400)

    def test_exception_releases_the_lock(self):
        with self.assertRaises(RuntimeError):
            self.client.post("/boom/", {"x": 1}, format="json", HTTP_IDEMPOTENCY_KEY="k3")
        with self.assertRaises(RuntimeError):
            self.client.post("/boom/", {"x": 1}, format="json", HTTP_IDEMPOTENCY_KEY="k3")

    def test_concurrent_twins_execute_the_view_once(self):
        """Régression : le verrou est posé AVANT le traitement.

        Deux requêtes concurrentes portant la même Idempotency-Key ne doivent
        déclencher qu'une seule exécution de la vue ; la perdante reçoit 409.
        """
        def fire():
            return APIClient().post("/slow/", {"x": 1}, format="json",
                                    HTTP_IDEMPOTENCY_KEY="race-key")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(fire), pool.submit(fire)]
            statuses = sorted(f.result().status_code for f in futures)

        self.assertEqual(CALLS["count"], 1, "la vue a été exécutée plus d'une fois")
        self.assertEqual(statuses, [200, 409])

    def test_conflict_payload_shape(self):
        cache.set("idem:" + __import__("hashlib").sha256(b"/slow/|inflight").hexdigest(),
                  {"state": "pending", "fingerprint": None, "ts": 0}, timeout=60)
        r = self.client.post("/slow/", {"x": 1}, format="json",
                             HTTP_IDEMPOTENCY_KEY="inflight")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "idempotency_in_progress")
        self.assertEqual(r["Retry-After"], "1")
