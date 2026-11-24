"""Maintenance des partitions mensuelles (Étape 2 §7).

Une partition manquante arrête toutes les écritures financières. Cette tâche
maintient trois mois d'avance et remonte une métrique : l'absence de partition
future doit déclencher une alerte *avant* l'incident, jamais après.
"""
from __future__ import annotations

import logging

from celery import shared_task

from apps.core.partitioning import MONTHS_AHEAD, PARTITIONED_TABLES, ensure_partitions

logger = logging.getLogger("muntu.partitioning")


@shared_task(name="muntu.core.ensure_partitions")
def ensure_partitions_task(months_ahead: int = MONTHS_AHEAD) -> dict:
    created = ensure_partitions(months_ahead=months_ahead)
    logger.info("Partitions vérifiées", extra={"created": created,
                                               "tables": list(PARTITIONED_TABLES)})
    return {"created": created, "months_ahead": months_ahead}
