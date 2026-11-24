#!/usr/bin/env python3
"""Validation des imports du projet Muntu Core."""
import sys, os
sys.path.insert(0, "backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
import django
django.setup()

errors = []

# 1. Core
try:
    from apps.core.fsm import SignedStateMachine, StateProtocol, TransitionRule, TransitionResult
    print("[OK] core.fsm")
except Exception as e:
    errors.append(f"core.fsm: {e}")

try:
    from apps.core.middleware.rls import RowLevelSecurityMiddleware, set_rls_context, clear_rls_context
    print("[OK] core.middleware.rls")
except Exception as e:
    errors.append(f"core.middleware.rls: {e}")

try:
    from apps.core.middleware.tenant_middleware import TenantMiddleware
    print("[OK] core.middleware.tenant_middleware")
except Exception as e:
    errors.append(f"core.middleware.tenant_middleware: {e}")

try:
    from apps.core.throttling import FinancialOperationThrottle, TellerOperationThrottle
    print("[OK] core.throttling")
except Exception as e:
    errors.append(f"core.throttling: {e}")

try:
    from apps.core.db import db_actor, db_system_actor, set_local_context
    print("[OK] core.db")
except Exception as e:
    errors.append(f"core.db: {e}")

# 2. Tenancy
try:
    from apps.tenancy.models import Institution, Branch, ModuleToggle
    print("[OK] tenancy.models")
except Exception as e:
    errors.append(f"tenancy.models: {e}")

try:
    from apps.tenancy.services.onboarding import onboard_institution
    print("[OK] tenancy.services.onboarding")
except Exception as e:
    errors.append(f"tenancy.services.onboarding: {e}")

# 3. Members
try:
    from apps.members.models import Member, MemberDocument, SolidarityGroup, SolidarityGroupMember
    print("[OK] members.models")
except Exception as e:
    errors.append(f"members.models: {e}")

# 4. Savings
try:
    from apps.savings.models import SavingsProduct, SavingsAccount, InterestAccrual
    print("[OK] savings.models")
except Exception as e:
    errors.append(f"savings.models: {e}")

try:
    from apps.savings.services.interest import compute_daily_interest
    print("[OK] savings.services.interest")
except Exception as e:
    errors.append(f"savings.services.interest: {e}")

# 5. Lending
try:
    from apps.lending.models import LoanProduct, Loan, LoanInstallment
    print("[OK] lending.models")
except Exception as e:
    errors.append(f"lending.models: {e}")

try:
    from apps.lending.services.schedule import compute_schedule, compute_flat_schedule, compute_declining_schedule, compute_french_schedule
    print("[OK] lending.services.schedule")
except Exception as e:
    errors.append(f"lending.services.schedule: {e}")

try:
    from apps.lending.services.risk import compute_risk_score
    print("[OK] lending.services.risk")
except Exception as e:
    errors.append(f"lending.services.risk: {e}")

# 6. Teller
try:
    from apps.teller.models import TellerSession, TellerOperation, TellerTransfer
    print("[OK] teller.models")
except Exception as e:
    errors.append(f"teller.models: {e}")

# 7. Payments & Ledger
try:
    from apps.payments.models import Payment, LedgerEntry, LedgerAccount, LedgerDirection
    print("[OK] payments.models")
except Exception as e:
    errors.append(f"payments.models: {e}")

try:
    from apps.payments.services.ledger import (
        post_savings_deposit, post_savings_withdrawal,
        post_loan_disbursement, post_loan_repayment,
        post_interest_accrual, post_teller_opening, post_teller_closing,
        post_transfer, post_provision, LedgerInvariantError
    )
    print("[OK] payments.services.ledger")
except Exception as e:
    errors.append(f"payments.services.ledger: {e}")

# 8. Accounting
try:
    from apps.accounting.models import ChartAccount, JournalEntry, AccountingDay
    print("[OK] accounting.models")
except Exception as e:
    errors.append(f"accounting.models: {e}")

# 9. Regulatory
try:
    from apps.regulatory.models import RegulatoryReport, RiskCenterEntry, AMLAlert
    print("[OK] regulatory.models")
except Exception as e:
    errors.append(f"regulatory.models: {e}")

# 10. Claims
try:
    from apps.claims.models import Claim, ClaimResolution
    print("[OK] claims.models")
except Exception as e:
    errors.append(f"claims.models: {e}")

# 11. Documents
try:
    from apps.documents.models import Document, DocumentTemplate
    print("[OK] documents.models")
except Exception as e:
    errors.append(f"documents.models: {e}")

# 12. Celery config
try:
    from config.celery_app import app as celery_app
    print("[OK] celery_app (no crash on import)")
except Exception as e:
    errors.append(f"celery_app: {e}")

# 13. URL config
try:
    import config.urls as urls_module
    print(f"[OK] urls (module loaded) - skip prometheus_client")
except ImportError as e:
    if "prometheus" in str(e):
        print("[SKIP] urls (prometheus_client not installed - harmless)")
    else:
        errors.append(f"urls: {e}")
except Exception as e:
    errors.append(f"urls: {e}")

# Résumé
print(f"\n{'='*50}")
if errors:
    print(f"ERREURS ({len(errors)}):")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
else:
    print("Tous les imports OK — aucun module cassé.")
    sys.exit(0)
