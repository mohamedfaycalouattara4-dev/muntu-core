"""Module de scoring alternatif par IA et gestion avancée des risques (Étapes 31 à 35) — Muntu-Core.
Fournit l'évaluation de solvabilité non bancarisée et le calcul du Portefeuille à Risque (PAR).
"""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger("muntu.risk")


class AIScoringEngine:
    """Moteur d'évaluation du risque de crédit basé sur l'historique comportemental et l'épargne."""

    @staticmethod
    def calculate_alternative_score(member_id: str, savings_stability_score: float, mobile_money_volume: Decimal) -> int:
        """Calcule un score de crédit de 0 à 1000 pour les emprunteurs non bancarisés."""
        base_score = 500
        stability_bonus = int(savings_stability_score * 300)
        volume_bonus = min(200, int(float(mobile_money_volume) / 100000 * 50))

        final_score = max(0, min(1000, base_score + stability_bonus + volume_bonus))
        logger.info(f"Score alternatif calculé pour le membre {member_id} : {final_score}/1000")
        return final_score


class PortfolioRiskEngine:
    """Calculateur des indicateurs prudentiels BCEAO (PAR 30, PAR 60, PAR 90)."""

    @staticmethod
    def evaluate_par(total_outstanding_portfolio: Decimal, overdue_portfolio: Decimal) -> float:
        """Calcule le Portefeuille à Risque en pourcentage."""
        if total_outstanding_portfolio <= 0:
            return 0.0
        par = (float(overdue_portfolio) / float(total_outstanding_portfolio)) * 100.0
        return round(par, 2)
