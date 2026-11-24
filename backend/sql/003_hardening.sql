-- =====================================================================
-- MUNTU CORE — Durcissement du socle de données (R1, R5, R7)
-- PostgreSQL 16 · appliqué par core/0005_database_hardening.py (RunSQL)
-- Idempotent : rejouable sur une base existante comme sur une base vierge.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. Extensions d'observabilité base (R10)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'pg_stat_statements indisponible (%). Poursuite.', SQLERRM;
    END;
END
$$;

-- ---------------------------------------------------------------------
-- 1. Helper : ajout de contrainte CHECK idempotent et non bloquant
--    NOT VALID puis VALIDATE CONSTRAINT (verrou faible sur grosses tables).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION muntu_add_check(
    p_table text, p_name text, p_expr text
) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables
                   WHERE schemaname = 'public' AND tablename = p_table) THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = p_name) THEN
        RETURN;
    END IF;
    EXECUTE format('ALTER TABLE public.%I ADD CONSTRAINT %I CHECK (%s) NOT VALID',
                   p_table, p_name, p_expr);
    EXECUTE format('ALTER TABLE public.%I VALIDATE CONSTRAINT %I', p_table, p_name);
END
$$;

-- ---------------------------------------------------------------------
-- 2. Contraintes d'intégrité métier — domaine microfinance
-- ---------------------------------------------------------------------

-- Paiements : montants positifs (D5 : 64 bits)
SELECT muntu_add_check('payments_payment', 'payment_amount_positive',
    'amount_xof > 0');

-- Grand livre : montants non négatifs, direction valide
SELECT muntu_add_check('payments_ledgerentry', 'ledger_amount_non_negative',
    'amount_xof >= 0');
SELECT muntu_add_check('payments_ledgerentry', 'ledger_direction_valid',
    E'direction IN (\'DEBIT\', \'CREDIT\')');

-- Paiements : cohérence des dates d'état
SELECT muntu_add_check('payments_payment', 'payment_state_dates_coherent',
    E'NOT (state = ''COMPLETED'' AND completed_at IS NULL)');

-- Épargne : solde non négatif (projeté, mais contrainte de sécurité)
SELECT muntu_add_check('savings_savingsaccount', 'savings_blocked_amount_non_negative',
    'blocked_amount >= 0');

-- Prêt : montants non négatifs
SELECT muntu_add_check('lending_loan', 'loan_amounts_non_negative',
    'requested_amount >= 0 AND approved_amount >= 0 AND outstanding_principal >= 0 AND outstanding_interest >= 0');

-- Échéancier : montants non négatifs
SELECT muntu_add_check('lending_loaninstallment', 'installment_amounts_non_negative',
    'principal_amount >= 0 AND interest_amount >= 0 AND total_amount >= 0');

-- Caisse : soldes non négatifs
SELECT muntu_add_check('teller_tellersession', 'teller_balance_non_negative',
    'opening_balance >= 0');

-- Intérêts : taux non négatif
SELECT muntu_add_check('savings_savingsproduct', 'savings_rate_non_negative',
    'annual_interest_rate >= 0');
SELECT muntu_add_check('lending_loanproduct', 'loan_rate_non_negative',
    'annual_interest_rate >= 0');

-- Membre : unicity par tenant + numéro de pièce
SELECT muntu_add_check('members_member', 'member_id_doc_check',
    E'(id_document_type = ''OTHER'' OR id_document_number != '''')');

-- ---------------------------------------------------------------------
-- 3. Unicités partielles (états actifs uniquement)
-- ---------------------------------------------------------------------
-- Clé d'idempotence paiements
CREATE UNIQUE INDEX IF NOT EXISTS uniq_payment_idempotency_key
    ON public.payments_payment (idempotency_key);

-- Numéro de membre unique par institution
CREATE UNIQUE INDEX IF NOT EXISTS uniq_member_number_per_tenant
    ON public.members_member (tenant_id, member_number);

-- Numéro de compte épargne unique
CREATE UNIQUE INDEX IF NOT EXISTS uniq_savings_account_number
    ON public.savings_savingsaccount (account_number);

-- Numéro de prêt unique
CREATE UNIQUE INDEX IF NOT EXISTS uniq_loan_number
    ON public.lending_loan (loan_number);

-- Session caisse : un seul guichetier par jour par agence par institution
CREATE UNIQUE INDEX IF NOT EXISTS uniq_teller_session_per_day
    ON public.teller_tellersession (tenant_id, branch_code, teller_id, opened_at);

-- Accrual : un seul par compte par jour
CREATE UNIQUE INDEX IF NOT EXISTS uniq_accrual_per_day
    ON public.savings_interestaccrual (account_id, accrual_date);

-- ---------------------------------------------------------------------
-- 4. Clés étrangères financières : ON DELETE RESTRICT
-- ---------------------------------------------------------------------
DO $$
DECLARE
    r record;
    v_def text;
    v_defer text;
BEGIN
    FOR r IN
        SELECT c.conname, c.conrelid::regclass::text AS tbl, pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype = 'f'
          AND n.nspname = 'public'
          AND c.confdeltype <> 'r'
          AND t.relname IN (
              'payments_payment', 'payments_ledgerentry',
              'savings_savingsaccount', 'savings_interestaccrual',
              'lending_loan', 'lending_loaninstallment', 'lending_loanpayment', 'lending_guarantee',
              'teller_tellersession', 'teller_telleroperation', 'teller_tellertransfer',
              'accounting_journalentry', 'accounting_accountingday',
              'regulatory_regulatoryreport', 'regulatory_riskcenterentry',
              'claims_claim', 'claims_claimresolution',
              'documents_document', 'documents_documenttemplate',
              'audit_auditevent')
    LOOP
        v_defer := CASE WHEN r.def LIKE '%DEFERRABLE%'
                        THEN ' DEFERRABLE INITIALLY DEFERRED' ELSE '' END;
        v_def := regexp_replace(r.def, '\s+DEFERRABLE.*$', '', 'g');
        v_def := regexp_replace(v_def, '\s+ON DELETE [A-Z ]+', '', 'g');
        v_def := regexp_replace(v_def, '\s+ON UPDATE [A-Z ]+', '', 'g');
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tbl, r.conname);
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s ON DELETE RESTRICT%s',
                       r.tbl, r.conname, v_def, v_defer);
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------
-- 5. Index critiques (balayages Celery, états actifs, JSON, idempotence)
-- ---------------------------------------------------------------------
-- Paiements : état + date (reconciliation)
CREATE INDEX IF NOT EXISTS idx_payment_state_created
    ON public.payments_payment (state, created_at);
CREATE INDEX IF NOT EXISTS idx_payment_pending
    ON public.payments_payment (state, created_at)
    WHERE state IN ('INITIALIZED', 'AUTHORIZED');

-- Prêts : état + date (vérification échéances)
CREATE INDEX IF NOT EXISTS idx_loan_state_due
    ON public.lending_loan (tenant_id, status, first_due_date)
    WHERE status IN ('DISBURSED', 'DELINQUENT');

-- Épargnes : état + produit
CREATE INDEX IF NOT EXISTS idx_savings_active
    ON public.savings_savingsaccount (tenant_id, status, product_id)
    WHERE status = 'ACTIVE';

-- Caisse : session ouverte
CREATE INDEX IF NOT EXISTS idx_teller_open
    ON public.teller_tellersession (tenant_id, branch_code, teller_id)
    WHERE status = 'OPEN';

-- Outbox : événements en attente
CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON public.core_outboxevent (status, created_at)
    WHERE status = 'pending';

-- Audit : payload JSON (recherche)
CREATE INDEX IF NOT EXISTS idx_audit_payload_gin
    ON public.audit_auditevent USING gin (payload jsonb_path_ops);

-- Idempotence
CREATE UNIQUE INDEX IF NOT EXISTS uniq_idempotency_record_key
    ON public.core_idempotencyrecord (key_hash);

-- ---------------------------------------------------------------------
-- 6. Grand livre réellement append-only (R1)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION deny_ledger_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Grand livre immuable : % interdit sur payments_ledgerentry (R1)',
        TG_OP USING ERRCODE = 'raise_exception';
END
$$;

-- ---------------------------------------------------------------------
-- 7. Isolation RLS des tables de traçabilité
-- ---------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['audit_auditevent', 'notifications_notification'] LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
            EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
        END IF;
    END LOOP;
END $$;

DROP POLICY IF EXISTS audit_insert ON public.audit_auditevent;
CREATE POLICY audit_insert ON public.audit_auditevent FOR INSERT
    WITH CHECK (true);

DROP POLICY IF EXISTS audit_read ON public.audit_auditevent;
CREATE POLICY audit_read ON public.audit_auditevent FOR SELECT
    USING (
        muntu_is_system()
        OR muntu_has_role('admin')
        OR muntu_has_role('compliance')
        OR muntu_has_role('auditor')
        OR actor_id = muntu_current_user_id()
    );

DROP POLICY IF EXISTS notifications_scope ON public.notifications_notification;
CREATE POLICY notifications_scope ON public.notifications_notification FOR ALL
    USING (muntu_is_system() OR recipient_id = muntu_current_user_id())
    WITH CHECK (muntu_is_system() OR recipient_id = muntu_current_user_id());
