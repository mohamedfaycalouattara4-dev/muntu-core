"""PaymentAggregatorAdapter · Pattern Adapter (V2 §9.5).

Durcissements P0-07 et P0-08 :

* **P0-07** — les adaptateurs simulés refusent de démarrer hors développement.
  Toute tentative d'utilisation dans un environnement non `dev`/`test` lève
  `SimulatedAdapterForbidden`, sauf activation *explicite* de
  `PAYMENTS_ALLOW_SIMULATED_ADAPTERS` (jamais activable quand
  `ENVIRONMENT == "production"`).
* **P0-08** — l'idempotence est mutualisée dans `IdempotentAdapterMixin` et
  appliquée à **tous** les adaptateurs (Wave, Orange Money, Moov, GIM, Generic),
  y compris `confirm`, `release` et `refund`. Un rejeu strictement identique
  renvoie le résultat mémorisé ; un rejeu avec une charge utile différente est
  rejeté (`DuplicatePaymentError`).
"""
from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("muntu.payments")

IDEMPOTENCY_TTL_SECONDS = 86_400


class AggregatorError(Exception):
    pass


class DuplicatePaymentError(AggregatorError):
    """Rejeu détecté avec une charge utile divergente : opération refusée."""


class SimulatedAdapterForbidden(AggregatorError):
    """Un adaptateur simulé a été sollicité hors environnement de développement."""


@dataclass
class Intent:
    aggregator_ref: str
    status: str  # PENDING / AUTHORIZED / CAPTURED / FAILED / RELEASED / REFUNDED


# ---------------------------------------------------------------------------
# Garde-fou environnement (P0-07)
# ---------------------------------------------------------------------------
def environment() -> str:
    return str(getattr(settings, "ENVIRONMENT", "dev")).lower()


def simulated_adapters_allowed() -> bool:
    if environment() in {"production", "prod", "staging"}:
        return False
    return bool(getattr(settings, "PAYMENTS_ALLOW_SIMULATED_ADAPTERS", False))


def assert_simulation_allowed(adapter_name: str) -> None:
    if not simulated_adapters_allowed():
        raise SimulatedAdapterForbidden(
            f"Adaptateur simulé « {adapter_name} » interdit dans l'environnement "
            f"« {environment()} ». Configurez un connecteur agrégateur réel ou "
            "activez explicitement PAYMENTS_ALLOW_SIMULATED_ADAPTERS en développement."
        )


# ---------------------------------------------------------------------------
# Idempotence (P0-08)
# ---------------------------------------------------------------------------
class IdempotentAdapterMixin:
    """Mémorisation atomique par (adaptateur, opération, clé)."""

    name: str = "ABSTRACT"

    def _idem_key(self, operation: str, key: str) -> str:
        return f"payadapter:{self.name}:{operation}:{key}"

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def idempotent(self, *, operation: str, key: str, payload: dict, producer):
        """Exécute `producer()` une seule fois pour une clé donnée.

        * même clé + même charge utile → résultat mémorisé, aucun nouvel appel ;
        * même clé + charge différente → `DuplicatePaymentError` ;
        * absence de clé → refus (une opération financière doit être rejouable
          sans risque de double débit).
        """
        if not key:
            raise AggregatorError(
                f"{self.name}.{operation} exige une clé d'idempotence.")
        cache_key = self._idem_key(operation, key)
        fingerprint = self._fingerprint(payload)

        stored = cache.get(cache_key)
        if stored is None:
            # `add` est atomique : il gagne la course entre deux rejeux simultanés.
            if not cache.add(cache_key, {"fingerprint": fingerprint, "state": "in_flight"},
                             timeout=IDEMPOTENCY_TTL_SECONDS):
                stored = cache.get(cache_key)
            else:
                try:
                    result = producer()
                except Exception:
                    cache.delete(cache_key)
                    raise
                cache.set(cache_key,
                          {"fingerprint": fingerprint, "state": "done",
                           "result": asdict(result) if isinstance(result, Intent) else result},
                          timeout=IDEMPOTENCY_TTL_SECONDS)
                return result

        if stored.get("fingerprint") != fingerprint:
            raise DuplicatePaymentError(
                f"Clé d'idempotence {key} déjà utilisée par {self.name}.{operation} "
                "avec une charge utile différente.")
        if stored.get("state") != "done":
            raise DuplicatePaymentError(
                f"Opération {self.name}.{operation} déjà en cours pour la clé {key}.")
        logger.info("Rejeu idempotent absorbé %s.%s key=%s", self.name, operation, key)
        result = stored.get("result")
        if isinstance(result, dict) and "aggregator_ref" in result:
            return Intent(**result)
        return result


class PaymentAggregatorAdapter(IdempotentAdapterMixin, ABC):
    """ABC à implémenter pour chaque provider."""

    name: str = "ABSTRACT"
    #: Un adaptateur simulé n'appelle aucun système de paiement réel.
    simulated: bool = False

    @abstractmethod
    def authorize(self, *, reference: str, amount_xof: int,
                  idempotency_key: str) -> Intent: ...

    @abstractmethod
    def confirm(self, *, aggregator_ref: str, idempotency_key: str = "") -> Intent: ...

    @abstractmethod
    def release(self, *, aggregator_ref: str, idempotency_key: str = "") -> None: ...

    @abstractmethod
    def refund(self, *, aggregator_ref: str, amount_xof: int,
               idempotency_key: str = "") -> None: ...

    @abstractmethod
    def query(self, *, aggregator_ref: str) -> Intent: ...


class SimulatedAdapter(PaymentAggregatorAdapter):
    """Base commune des adaptateurs de démonstration (aucun flux monétaire réel)."""

    simulated = True
    prefix = "SIM"

    def _guard(self) -> None:
        assert_simulation_allowed(self.name)

    def authorize(self, *, reference, amount_xof, idempotency_key):
        self._guard()
        if int(amount_xof) <= 0:
            raise AggregatorError("Montant d'autorisation invalide.")
        return self.idempotent(
            operation="authorize", key=idempotency_key,
            payload={"reference": reference, "amount_xof": int(amount_xof)},
            producer=lambda: Intent(
                aggregator_ref=f"{self.prefix}-{reference}-{idempotency_key[:8]}",
                status="AUTHORIZED"))

    def confirm(self, *, aggregator_ref, idempotency_key=""):
        self._guard()
        return self.idempotent(
            operation="confirm", key=idempotency_key or aggregator_ref,
            payload={"aggregator_ref": aggregator_ref},
            producer=lambda: Intent(aggregator_ref=aggregator_ref, status="CAPTURED"))

    def release(self, *, aggregator_ref, idempotency_key=""):
        self._guard()

        def _do():
            logger.info("%s release %s", self.name, aggregator_ref)
            return Intent(aggregator_ref=aggregator_ref, status="RELEASED")

        self.idempotent(operation="release", key=idempotency_key or aggregator_ref,
                        payload={"aggregator_ref": aggregator_ref}, producer=_do)

    def refund(self, *, aggregator_ref, amount_xof, idempotency_key=""):
        self._guard()

        def _do():
            logger.info("%s refund %s amount=%s", self.name, aggregator_ref, amount_xof)
            return Intent(aggregator_ref=aggregator_ref, status="REFUNDED")

        self.idempotent(
            operation="refund",
            key=idempotency_key or f"{aggregator_ref}:{amount_xof}",
            payload={"aggregator_ref": aggregator_ref, "amount_xof": int(amount_xof)},
            producer=_do)

    def query(self, *, aggregator_ref):
        self._guard()
        return Intent(aggregator_ref=aggregator_ref, status="CAPTURED")


class WaveAdapter(SimulatedAdapter):
    name = "WAVE"
    prefix = "WAVE"


class OrangeMoneyAdapter(SimulatedAdapter):
    name = "ORANGE_MONEY"
    prefix = "OM"


class MoovAdapter(SimulatedAdapter):
    name = "MOOV"
    prefix = "MOOV"


class GIMUEMOAAdapter(SimulatedAdapter):
    name = "GIM_UEMOA"
    prefix = "GIM"


class GenericAdapter(SimulatedAdapter):
    name = "GENERIC"
    prefix = "GEN"


class AggregatorRegistry:
    def __init__(self):
        self._registry: dict[str, PaymentAggregatorAdapter] = {
            "WAVE": WaveAdapter(),
            "ORANGE_MONEY": OrangeMoneyAdapter(),
            "MOOV": MoovAdapter(),
            "GIM_UEMOA": GIMUEMOAAdapter(),
        }
        self._default = GenericAdapter()

    def register(self, adapter: PaymentAggregatorAdapter) -> None:
        """Point d'extension pour les connecteurs réels (production)."""
        self._registry[adapter.name.upper()] = adapter

    def get(self, provider: str) -> PaymentAggregatorAdapter:
        adapter = self._registry.get((provider or "").upper(), self._default)
        if adapter.simulated:
            # Refus explicite AVANT toute écriture financière (P0-07).
            assert_simulation_allowed(adapter.name)
        return adapter

    def list_providers(self) -> list[str]:
        return list(self._registry.keys())


registry = AggregatorRegistry()
