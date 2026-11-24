-- =====================================================================
-- MUNTU CORE — Row-Level Security réellement opérationnelle
-- PostgreSQL 16
--
-- Appliqué par la migration Django `core/0002_row_level_security.py`.
--
-- Principes :
--   1. FORCE ROW LEVEL SECURITY sur toutes les tables sensibles
--   2. Rôle applicatif `muntu_app` NOBYPASSRLS (Django ne contourne pas RLS)
--   3. Contexte porté par variables de session (tenant_id, user_id, role)
--   4. Isolation stricte : tenant_id est le pivot de TOUTE politique
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Rôle applicatif (non propriétaire, NOBYPASSRLS)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'muntu_app') THEN
        CREATE ROLE muntu_app NOLOGIN NOBYPASSRLS;
    ELSE
        ALTER ROLE muntu_app NOBYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO muntu_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO muntu_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO muntu_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO muntu_app;

-- ---------------------------------------------------------------------
-- 2. Helpers de contexte (STABLE, search_path figé)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION muntu_tenant_id() RETURNS text
    LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $$
    SELECT nullif(current_setting('muntu.tenant_id', true), '')
$$;

CREATE OR REPLACE FUNCTION muntu_current_user_id() RETURNS text
    LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $$
    SELECT nullif(current_setting('muntu.current_user_id', true), '')
$$;

CREATE OR REPLACE FUNCTION muntu_roles() RETURNS text[]
    LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $$
    SELECT coalesce(
        string_to_array(nullif(current_setting('muntu.role', true), ''), ','),
        ARRAY[]::text[])
$$;

CREATE OR REPLACE FUNCTION muntu_has_role(VARIADIC wanted text[]) RETURNS boolean
    LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $$
    SELECT muntu_roles() && wanted
$$;

-- Tâches de fond / migrations : contexte système explicite et tracé.
CREATE OR REPLACE FUNCTION muntu_is_system() RETURNS boolean
    LANGUAGE sql STABLE SET search_path = pg_catalog, public AS $$
    SELECT coalesce(current_setting('muntu.system', true), 'off') = 'on'
$$;

-- ---------------------------------------------------------------------
-- 3. Activation + FORCE sur toutes les tables tenant-scoped
-- ---------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tenancy_institution',
        'tenancy_branch',
        'tenancy_moduletoggle',
        'members_member',
        'members_memberdocument',
        'members_solidaritygroup',
        'members_solidaritygroupmember',
        'savings_savingsproduct',
        'savings_savingsaccount',
        'savings_interestaccrual',
        'lending_loanproduct',
        'lending_loan',
        'lending_loaninstallment',
        'lending_loanpayment',
        'lending_guarantee',
        'teller_tellersession',
        'teller_telleroperation',
        'teller_tellertransfer',
        'accounting_chartaccount',
        'accounting_journalentry',
        'accounting_accountingday',
        'payments_payment',
        'payments_ledgerentry',
        'regulatory_regulatoryreport',
        'regulatory_riskcenterentry',
        'regulatory_amlalert',
        'claims_claim',
        'claims_claimresolution',
        'documents_document',
        'documents_documenttemplate',
        'accounts_user',
        'audit_auditevent',
        'risk_amlalert'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = t) THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
            EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------
-- 4. Politiques — TENANCY (institution, branches, modules)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS institution_tenant_scope ON public.tenancy_institution;
CREATE POLICY institution_tenant_scope ON public.tenancy_institution FOR ALL
    USING (
        muntu_is_system()
        OR id = muntu_tenant_id()
    )
    WITH CHECK (
        muntu_is_system()
        OR muntu_has_role('admin', 'superadmin')
    );

DROP POLICY IF EXISTS branch_tenant_scope ON public.tenancy_branch;
-- `tenancy_branch` ne porte pas de colonne tenant_id : le tenant est
-- l'institution parente (cle etrangere `institution_id`).
CREATE POLICY branch_tenant_scope ON public.tenancy_branch FOR ALL
    USING (
        muntu_is_system()
        OR institution_id = muntu_tenant_id()
    )
    WITH CHECK (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator')
    );

-- ---------------------------------------------------------------------
-- 5. Politiques — MEMBERS (membres, KYC, groupes)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS member_tenant_scope ON public.members_member;
CREATE POLICY member_tenant_scope ON public.members_member FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator', 'finance', 'teller', 'credit_officer')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator', 'teller')
    );

DROP POLICY IF EXISTS member_doc_tenant_scope ON public.members_memberdocument;
CREATE POLICY member_doc_tenant_scope ON public.members_memberdocument FOR ALL
    USING (
        muntu_is_system()
        OR EXISTS (SELECT 1 FROM public.members_member m
                   WHERE m.id = members_memberdocument.member_id
                     AND m.tenant_id = muntu_tenant_id())
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'operator', 'compliance'));

DROP POLICY IF EXISTS solidarity_group_tenant_scope ON public.members_solidaritygroup;
CREATE POLICY solidarity_group_tenant_scope ON public.members_solidaritygroup FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'operator'));

-- ---------------------------------------------------------------------
-- 6. Politiques — SAVINGS (épargne)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS savings_product_tenant_scope ON public.savings_savingsproduct;
CREATE POLICY savings_product_tenant_scope ON public.savings_savingsproduct FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'finance'));

DROP POLICY IF EXISTS savings_account_tenant_scope ON public.savings_savingsaccount;
CREATE POLICY savings_account_tenant_scope ON public.savings_savingsaccount FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator', 'finance', 'teller', 'compliance')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'operator', 'teller'));

DROP POLICY IF EXISTS interest_accrual_tenant_scope ON public.savings_interestaccrual;
CREATE POLICY interest_accrual_tenant_scope ON public.savings_interestaccrual FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    );

-- ---------------------------------------------------------------------
-- 7. Politiques — LENDING (crédit)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS loan_product_tenant_scope ON public.lending_loanproduct;
CREATE POLICY loan_product_tenant_scope ON public.lending_loanproduct FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'finance'));

DROP POLICY IF EXISTS loan_tenant_scope ON public.lending_loan;
CREATE POLICY loan_tenant_scope ON public.lending_loan FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator', 'finance', 'credit_officer', 'compliance')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (
        muntu_is_system()
        OR muntu_has_role('admin', 'credit_officer')
    );

DROP POLICY IF EXISTS loan_payment_tenant_scope ON public.lending_loanpayment;
CREATE POLICY loan_payment_tenant_scope ON public.lending_loanpayment FOR ALL
    USING (
        muntu_is_system()
        OR EXISTS (SELECT 1 FROM public.lending_loan l
                   WHERE l.id = lending_loanpayment.loan_id
                     AND l.tenant_id = muntu_tenant_id())
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'teller', 'finance'));

-- ---------------------------------------------------------------------
-- 8. Politiques — TELLER (caisse)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS teller_session_tenant_scope ON public.teller_tellersession;
CREATE POLICY teller_session_tenant_scope ON public.teller_tellersession FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'teller', 'finance', 'compliance')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'teller'));

DROP POLICY IF EXISTS teller_operation_tenant_scope ON public.teller_telleroperation;
CREATE POLICY teller_operation_tenant_scope ON public.teller_telleroperation FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'teller'));

-- ---------------------------------------------------------------------
-- 9. Politiques — ACCOUNTING (comptabilité)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS accounting_entry_tenant_scope ON public.accounting_journalentry;
CREATE POLICY accounting_entry_tenant_scope ON public.accounting_journalentry FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'finance', 'compliance', 'auditor')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'finance'));

-- ---------------------------------------------------------------------
-- 10. Politiques — PAYMENTS & LEDGER (paiements & grand livre)
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS payment_tenant_scope ON public.payments_payment;
CREATE POLICY payment_tenant_scope ON public.payments_payment FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'finance', 'compliance', 'auditor')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'finance', 'teller'));

-- Grand livre : append-only, lecture restreinte
DROP POLICY IF EXISTS ledger_tenant_scope ON public.payments_ledgerentry;
CREATE POLICY ledger_tenant_scope ON public.payments_ledgerentry FOR SELECT
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'finance', 'compliance', 'auditor')
        OR tenant_id = muntu_tenant_id()
    );

DROP POLICY IF EXISTS ledger_insert_tenant_scope ON public.payments_ledgerentry;
CREATE POLICY ledger_insert_tenant_scope ON public.payments_ledgerentry FOR INSERT
    WITH CHECK (
        muntu_is_system()
        OR muntu_has_role('admin', 'finance')
    );

-- Trigger deny sur UPDATE/DELETE du grand livre (append-only)
DROP TRIGGER IF EXISTS deny_ledger_mutation ON public.payments_ledgerentry;
CREATE OR REPLACE FUNCTION deny_ledger_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Grand livre immuable : UPDATE/DELETE interdits sur payments_ledgerentry.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER deny_ledger_mutation
    BEFORE UPDATE OR DELETE ON public.payments_ledgerentry
    FOR EACH ROW EXECUTE FUNCTION deny_ledger_mutation();

-- ---------------------------------------------------------------------
-- 11. Politiques — REGULATORY, CLAIMS, DOCUMENTS
-- ---------------------------------------------------------------------
DROP POLICY IF EXISTS regulatory_tenant_scope ON public.regulatory_regulatoryreport;
CREATE POLICY regulatory_tenant_scope ON public.regulatory_regulatoryreport FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'finance', 'compliance', 'auditor')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'compliance'));

DROP POLICY IF EXISTS claim_tenant_scope ON public.claims_claim;
CREATE POLICY claim_tenant_scope ON public.claims_claim FOR ALL
    USING (
        muntu_is_system()
        OR muntu_has_role('admin', 'operator', 'compliance')
        OR tenant_id = muntu_tenant_id()
    )
    WITH CHECK (muntu_is_system() OR muntu_has_role('admin', 'operator', 'compliance'));

DROP POLICY IF EXISTS document_tenant_scope ON public.documents_document;
CREATE POLICY document_tenant_scope ON public.documents_document FOR ALL
    USING (
        muntu_is_system()
        OR tenant_id = muntu_tenant_id()
    );
