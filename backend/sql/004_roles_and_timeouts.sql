-- =====================================================================
-- MUNTU CORE — Rôles PostgreSQL et garde-fous de session
-- Deux rôles distincts (§10.3) :
--   * propriétaire  : possède les tables, exécute les migrations ;
--   * applicatif    : NOSUPERUSER, NOBYPASSRLS, non-propriétaire, DML seul.
-- Seule cette configuration rend la RLS réellement opposable.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Rôle applicatif (groupe hérité par le rôle de connexion runtime)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'muntu_app') THEN
        CREATE ROLE muntu_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    ELSE
        ALTER ROLE muntu_app NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO muntu_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO muntu_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO muntu_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO muntu_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO muntu_app;

-- ---------------------------------------------------------------------
-- 2. Grand livre : révocation explicite de UPDATE/DELETE (R1)
--    Le trigger `deny_ledger_mutation` est la ceinture ; ceci est la bretelle.
-- ---------------------------------------------------------------------
REVOKE UPDATE, DELETE, TRUNCATE ON public.payments_ledgerentry FROM muntu_app;
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_auditevent FROM muntu_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO muntu_app;

-- ---------------------------------------------------------------------
-- 3. Garde-fous de session du rôle applicatif (R10)
--    Une transaction oubliée sur une table critique bloque un live entier.
-- ---------------------------------------------------------------------
ALTER ROLE muntu_app SET statement_timeout = '15s';
ALTER ROLE muntu_app SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE muntu_app SET lock_timeout = '5s';
