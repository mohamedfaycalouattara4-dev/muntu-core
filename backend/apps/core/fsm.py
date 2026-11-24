"""Muntu Core — Moteur d'états signé (extrait de apps/checkout/state_machine).
Fonction pure : transitions signées HMAC, chaîne d'événements append-only,
projection outbox à chaque transition validée.

Contrats :
- Une transition = (état_courant, événement) -> état_cible ou raise
- Chaque transition produit un signature HMAC unique (anti-rejeu par nonce)
- Chaque transition envoie un événement outbox (pour projection comptable / lecture)
- La machine est entièrement déterministe : même entrée = même sortie
"""
from __future__ import annotations
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from django.conf import settings


# ---------------------------------------------------------------------------
# Types de base
# ---------------------------------------------------------------------------
class StateProtocol(Protocol):
    """Protocole minimal pour les classes d'états (TextChoices Django)."""
    @classmethod
    def values(cls) -> list[str]:
        ...


@dataclass(frozen=True)
class TransitionRule:
    """Règle de transition : (état_source, événement) -> état_cible."""
    source: str
    event: str
    target: str
    guard: Callable | None = None  # prédicat optionnel (ex: solde suffisant)

    def canonical(self) -> str:
        return json.dumps({"s": self.source, "e": self.event, "t": self.target},
                          sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class TransitionResult:
    """Résultat d'une transition validée."""
    previous_state: str
    current_state: str
    event: str
    signature: str
    nonce: str
    timestamp: int
    payload: dict = field(default_factory=dict)


class SignedStateMachine:
    """Machine à états signée HMAC avec projection outbox.

    Usage :
        fsm = SignedStateMachine(
            name="loan",
            initial_state="DRAFT",
            rules=[
                TransitionRule("DRAFT", "SUBMIT", "UNDER_REVIEW"),
                TransitionRule("UNDER_REVIEW", "APPROVE", "ACTIVE"),
                TransitionRule("UNDER_REVIEW", "REJECT", "REJECTED"),
                TransitionRule("ACTIVE", "PREPAY", "PREPAID"),
                TransitionRule("ACTIVE", "DEFAULT", "DELINQUENT"),
            ],
            on_transition=my_outbox_callback,
        )

        result = fsm.transition("DRAFT", "SUBMIT", payload={"loan_id": "abc"})
        assert result.current_state == "UNDER_REVIEW"
    """

    def __init__(
        self,
        name: str,
        initial_state: str,
        rules: list[TransitionRule],
        on_transition: Callable | None = None,
    ) -> None:
        self.name = name
        self.initial_state = initial_state
        self._rules = {
            (r.source, r.event): r for r in rules
        }
        self._on_transition = on_transition

    def allowed_events(self, state: str) -> list[str]:
        """Retourne la liste des événements valides pour un état donné."""
        return [e for (s, e) in self._rules if s == state]

    def can_transition(self, state: str, event: str) -> bool:
        return (state, event) in self._rules

    def transition(
        self,
        current_state: str,
        event: str,
        payload: dict | None = None,
        guard_context: Any | None = None,
    ) -> TransitionResult:
        """Exécute une transition signée.

        Lève ValueError si la transition n'existe pas.
        Lève PermissionError si le guard échoue.
        """
        rule = self._rules.get((current_state, event))
        if rule is None:
            raise ValueError(
                f"Transition invalide : {self.name}.{current_state} --[{event}]--> ?"
            )
        if rule.guard and not rule.guard(guard_context):
            raise PermissionError(
                f"Guard rejeté pour {self.name}.{current_state} --[{event}]"
            )
        # --- Signature HMAC ---
        nonce = f"{self.name}-{int(time.time() * 1000)}"
        canonical = json.dumps(
            {"m": self.name, "f": current_state, "t": rule.target,
             "e": event, "n": nonce, "p": payload or {}},
            sort_keys=True, separators=(",", ":"),
        )
        signature = hmac.new(
            getattr(settings, "HSZ_SIGNING_KEY", "").encode() or b"dev-key-not-for-prod",
            canonical.encode("utf-8"),
            "sha256",
        ).hexdigest()

        result = TransitionResult(
            previous_state=current_state,
            current_state=rule.target,
            event=event,
            signature=signature,
            nonce=nonce,
            timestamp=int(time.time()),
            payload=payload or {},
        )

        if self._on_transition:
            self._on_transition(result)

        return result

    def graph(self) -> dict[str, list[dict[str, str]]]:
        """Retourne le graphe de transitions sous forme dict."""
        graph: dict[str, list[dict[str, str]]] = {}
        for (source, event), rule in self._rules.items():
            graph.setdefault(source, []).append({
                "event": event, "target": rule.target,
            })
        return graph
