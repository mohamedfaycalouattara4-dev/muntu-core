# Kalyce v1.0 — Correctifs P0 (audit sécurité)

| Réf | Défaut | Correctif |
|-----|--------|-----------|
| P0-01 | Décision de litige ouverte à tout authentifié | `IsArbitrator` + `HasVerifiedWebAuthn` + récusation (arbitre partie à la commande) |
| P0-02 | Quorum = comptage de chaînes | `verify_quorum` : N approbateurs distincts, assertions WebAuthn vérifiées et liées à l'empreinte de l'opération |
| P0-03 | WebAuthn factice (en-tête non vide) | `apps/core/webauthn.py` : FIDO2 réel (ES256/RS256/EdDSA, CBOR/COSE, signCount, challenge, origine, RP ID) |
| P0-04 | Gel global de la plateforme sur 1 alerte AML | Gel ciblé du compte + escalade SOC ; gel global strictement manuel |
| P0-05 | Clés de chiffrement codées en dur | Aucune dérivation de repli ; `ImproperlyConfigured` hors dev + system checks au démarrage |
| P0-06 | RLS documentaire (mauvaises tables, jamais appliquée) | `sql/002_rls_policies.sql` réécrit (vraies tables Django, FORCE RLS, rôle `kalyce_app` NOBYPASSRLS), appliqué par la migration `core.0002_row_level_security`, contexte posé par `RowLevelSecurityMiddleware` + `RLSJWTAuthentication` + contexte système Celery |
| P0-07 | Adaptateurs de paiement simulés | `assert_simulation_allowed` : interdits en staging/production, contrôle bloquant au démarrage |
| P0-08 | Idempotence absente (Moov, GIM, générique) | `IdempotentAdapterMixin` (cache `add` atomique) sur tous les adaptateurs |
| P0-09 | `startswith` sur le type d'acteur FSM | Égalité stricte |

## Déploiement
1. Variables obligatoires en production : `FIELD_ENCRYPTION_KEY`, `HSZ_SIGNING_KEY`, `AUDIT_SIGNING_KEY`, `DJANGO_SECRET_KEY`, `WEBAUTHN_RP_ID`, `WEBAUTHN_ALLOWED_ORIGINS`, `DB_APP_USER`/`DB_APP_PASSWORD`.
2. `python manage.py migrate` applique la RLS.
3. Le rôle applicatif ne doit **pas** être propriétaire des tables (sinon la RLS est contournée).
4. `pytest tests/security/test_p0_regressions.py` verrouille les 9 correctifs.
