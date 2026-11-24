-- KALYCE V2 — Contraintes PostgreSQL (à exécuter après migrate)
-- Postgres-first strategy · ULID opaque · check constraints stricts · RLS

-- 1. CHECK constraints durcies sur les stocks (anti-survente)
ALTER TABLE catalog_stock
    ADD CONSTRAINT stock_non_negative
        CHECK (quantity_total >= 0 AND quantity_reserved >= 0 AND quantity_sold >= 0),
    ADD CONSTRAINT stock_integrity
        CHECK (quantity_reserved + quantity_sold <= quantity_total);

-- 2. Index fonctionnels pour la recherche par hash (phone, idempotency, otp)
CREATE UNIQUE INDEX IF NOT EXISTS users_phone_hash_idx
    ON accounts_user (phone_hash);
CREATE UNIQUE INDEX IF NOT EXISTS orders_idempotency_key_idx
    ON payments (idempotency_key);
CREATE UNIQUE INDEX IF NOT EXISTS delivery_seals_order_id_idx
    ON delivery_seals (order_id);

-- 3. Trigger append-only sur le ledger
CREATE OR REPLACE FUNCTION deny_ledger_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ledger_entries is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE RULE no_update_ledger AS
    ON UPDATE TO ledger_entries DO INSTEAD NOTHING;
CREATE RULE no_delete_ledger AS
    ON DELETE TO ledger_entries DO INSTEAD NOTHING;
