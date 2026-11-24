"""Muntu Core — Grand livre : double-entry bookkeeping + invariants.

Toutes les écritures sont équilibrées (Σ DEBIT == Σ CREDIT).
Chaque entrée est chaînée par hash (intégrité I5).
Domaine : microfinance (épargne, crédit, caisse).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Iterable

from django.db import connection, transaction

from apps.core.security import sign_hmac

from ..models import LedgerAccount, LedgerDirection, LedgerEntry

logger = logging.getLogger("muntu.payments.ledger")


class LedgerInvariantError(Exception):
    """Violée quand la somme nulle ou l'intégrité HMAC est compromise."""
    pass


@dataclass(frozen=True)
class Posting:
    """Une ligne de journal : compte + direction + montant."""
    account: str
    direction: str  # DEBIT / CREDIT
    amount_xof: int


def _hash(prev: str, payload: str) -> str:
    return hashlib.sha256(f"{prev}|{payload}".encode()).hexdigest()


GENESIS_HASH = "0" * 64


def _lock_tenant_chain(tenant_id: str) -> None:
    """Sérialise les écritures d'un tenant (verrou consultatif transactionnel).

    Le verrou est porté par le tenant : deux institutions écrivent en parallèle
    sans contention (D5), tandis que la chaîne d'un tenant reste strictement
    séquentielle. No-op hors PostgreSQL.
    """
    if connection.vendor != "postgresql":  # pragma: no cover - parité locale
        return
    key = int.from_bytes(hashlib.sha256(tenant_id.encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def get_last_hash(tenant_id: str) -> str:
    """Dernier hash de la chaîne **du tenant** (racine de la nouvelle entrée).

    Dette D5 corrigée : chaque institution possède sa propre chaîne HMAC.
    Chaîner toutes les institutions sur un seul fil provoquait (a) une
    contention d'écriture globale entre clients et (b) une fuite du volume
    d'activité d'une institution vers les autres (le hash précédent révèle
    l'existence d'écritures voisines).

    Args:
        tenant_id: Identifiant de l'institution (obligatoire, invariant I2).

    Returns:
        Le hash de la dernière entrée du tenant, ou le hash de genèse.

    Raises:
        LedgerInvariantError: Si `tenant_id` est vide.
    """
    if not tenant_id:
        raise LedgerInvariantError("tenant_id obligatoire (isolation I2)")
    last = (
        LedgerEntry.objects.filter(tenant_id=tenant_id)
        .order_by("-id")
        .values("entry_hash")
        .first()
    )
    return last["entry_hash"] if last else GENESIS_HASH


def post_double_entry(
    reference: str,
    postings: Iterable[Posting],
    *,
    tenant_id: str,
    recorded_by: str = "system",
    day_id: str = "",
) -> list[LedgerEntry]:
    """Poste N écritures équilibrées (Σ DEBIT == Σ CREDIT).

    Invariant I1 : aucune écriture hors grand livre.
    Invariant I2 : tenant_id obligatoire pour isolation.

    Args:
        reference: Référence métier (ex: SAV-0001-DEP-500000).
        postings: Liste des lignes (Posting).
        tenant_id: Identifiant de l'institution (isolation).
        recorded_by: ULID de l'agent qui enregistre.
        day_id: Référence à AccountingDay (scellement quotidien).

    Returns:
        Liste des LedgerEntry créées.

    Raises:
        LedgerInvariantError: Si la somme nulle est violée ou les montants sont nuls.
    """
    if not tenant_id:
        raise LedgerInvariantError("tenant_id obligatoire (isolation I2)")
    posts = list(postings)
    if any(p.amount_xof < 0 for p in posts):
        raise LedgerInvariantError("Montants négatifs interdits")
    total_debit = sum(p.amount_xof for p in posts if p.direction == "DEBIT")
    total_credit = sum(p.amount_xof for p in posts if p.direction == "CREDIT")
    if total_debit != total_credit:
        raise LedgerInvariantError(
            f"Somme nulle violée : DEBIT={total_debit} vs CREDIT={total_credit}")
    if total_debit <= 0:
        raise LedgerInvariantError("Écritures nulles interdites")

    try:
        with transaction.atomic():
            _lock_tenant_chain(tenant_id)
            previous = get_last_hash(tenant_id)
            entries: list[LedgerEntry] = []
            for posting in posts:
                payload = (f"{tenant_id}|{reference}|{posting.account}"
                           f"|{posting.direction}|{posting.amount_xof}")
                entry_hash = _hash(previous, payload)
                signature = sign_hmac(entry_hash, "HSZ_SIGNING_KEY")
                entry = LedgerEntry.objects.create(
                    tenant_id=tenant_id,
                    account=posting.account,
                    direction=posting.direction,
                    amount_xof=posting.amount_xof,
                    reference=reference,
                    previous_hash=previous,
                    entry_hash=entry_hash,
                    signature=signature,
                    recorded_by=recorded_by,
                    day_id=day_id,
                )
                previous = entry_hash
                entries.append(entry)
                logger.info("ledger_entry_posted", extra={
                    "ledger_entry_id": str(entry.id),
                    "tenant_id": tenant_id,
                    "account": posting.account,
                    "direction": posting.direction,
                    "amount_xof": posting.amount_xof,
                    "entry_hash": entry_hash,
                    "previous_hash": entry.previous_hash,
                    "recorded_by": recorded_by,
                })
    except Exception:
        logger.exception("ledger_posting_failed", extra={
            "postings": len(posts), "amount_xof": total_debit, "reference": reference,
        })
        raise

    logger.info("ledger_transaction_posted", extra={
        "entries": len(entries),
        "amount_xof": total_debit,
        "tenant_id": tenant_id,
        "reference": reference,
        "recorded_by": recorded_by,
    })
    return entries


# ---------------------------------------------------------------------
# Helpers métier — domaine microfinance
# ---------------------------------------------------------------------

def post_savings_deposit(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Dépôt d'épargne : Caisse débitée, Compte épargne crédité."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.CASH, LedgerDirection.CREDIT, amount_xof),
        Posting(LedgerAccount.SAVINGS_DEPOSIT, LedgerDirection.DEBIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_savings_withdrawal(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Retrait d'épargne : Compte épargne débité, Caisse créditée."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.SAVINGS_DEPOSIT, LedgerDirection.CREDIT, amount_xof),
        Posting(LedgerAccount.CASH, LedgerDirection.DEBIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_loan_disbursement(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Décaissement d'un prêt : Caisse débitée, Prêt crédité (actif)."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.CASH, LedgerDirection.CREDIT, amount_xof),
        Posting(LedgerAccount.LOAN_DISBURSEMENT, LedgerDirection.DEBIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_loan_repayment(
    *, reference: str, principal_xof: int, interest_xof: int,
    fee_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Règlement de prêt : Caisse créditée, Prêt/Intérêts/Frais débités."""
    total = principal_xof + interest_xof + fee_xof
    postings = [
        Posting(LedgerAccount.CASH, LedgerDirection.DEBIT, total),
    ]
    if principal_xof > 0:
        postings.append(Posting(LedgerAccount.LOAN_PRINCIPAL, LedgerDirection.CREDIT, principal_xof))
    if interest_xof > 0:
        postings.append(Posting(LedgerAccount.LOAN_REPAYMENT, LedgerDirection.CREDIT, interest_xof))
    if fee_xof > 0:
        postings.append(Posting(LedgerAccount.FEE_REVENUE, LedgerDirection.CREDIT, fee_xof))
    return post_double_entry(reference, postings, tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_interest_accrual(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Provision d'intérêts créditeurs : Charge d'intérêts débitée, Intérêts créditeurs crédités."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.INTEREST_EXPENSE, LedgerDirection.DEBIT, amount_xof),
        Posting(LedgerAccount.INTEREST_INCOME, LedgerDirection.CREDIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_provision(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Provision pour dépréciation : Charge débitée, Provision créditée."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.PROVISION_EXPENSE, LedgerDirection.DEBIT, amount_xof),
        Posting(LedgerAccount.LOAN_PRINCIPAL, LedgerDirection.CREDIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_teller_opening(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Dotation d'ouverture caisse : Coffre débité, Caisse créditée."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.CASH, LedgerDirection.DEBIT, amount_xof),
        Posting(LedgerAccount.TRANSFER_OUT, LedgerDirection.CREDIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_teller_closing(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Remise de clôture caisse : Caisse débitée, Coffre crédité."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.TRANSFER_IN, LedgerDirection.DEBIT, amount_xof),
        Posting(LedgerAccount.CASH, LedgerDirection.CREDIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)


def post_transfer(
    *, reference: str, amount_xof: int, tenant_id: str,
    recorded_by: str = "system", day_id: str = "",
) -> list[LedgerEntry]:
    """Transfert inter-caisses : Transfert sortant débité, Transfert entrant crédité."""
    return post_double_entry(reference, [
        Posting(LedgerAccount.TRANSFER_OUT, LedgerDirection.DEBIT, amount_xof),
        Posting(LedgerAccount.TRANSFER_IN, LedgerDirection.CREDIT, amount_xof),
    ], tenant_id=tenant_id, recorded_by=recorded_by, day_id=day_id)
