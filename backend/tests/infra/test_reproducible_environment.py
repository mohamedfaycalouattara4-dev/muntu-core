"""J0 · L'environnement reproductible est vérifié par des tests (R5).

Un contrôle d'infrastructure non testé dérive silencieusement : ces tests
échouent si l'on retire le non-root de l'image, si l'on dégrade une image en
« latest », si une variable obligatoire disparaît de `.env.example`, ou si une
cible `make` documentée est supprimée.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"


def read(path: Path) -> str:
    assert path.exists(), f"Fichier d'infrastructure manquant : {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- Dockerfiles
class TestBackendImage:
    dockerfile = property(lambda self: read(BACKEND / "Dockerfile"))

    def test_image_est_multi_etages(self):
        stages = re.findall(r"^FROM .+ AS (\w+)", self.dockerfile, re.M)
        assert "builder" in stages and "runtime" in stages

    def test_execution_non_root(self):
        content = self.dockerfile
        assert re.search(r"^USER 10001", content, re.M), "L'image doit tourner en non-root"
        assert content.rstrip().index("USER 10001") < content.rstrip().index("ENTRYPOINT")

    def test_healthcheck_present(self):
        assert "HEALTHCHECK" in self.dockerfile and "/health" in self.dockerfile

    def test_asgi_gunicorn_uvicorn(self):
        content = self.dockerfile
        assert "config.asgi:application" in content
        assert "uvicorn.workers.UvicornWorker" in content

    def test_aucune_image_de_base_flottante(self):
        for line in re.findall(r"^FROM (\S+)", self.dockerfile, re.M):
            assert ":" in line, f"Image non épinglée : {line}"
            assert not line.endswith(":latest"), f"Tag latest interdit : {line}"

    def test_installation_par_lock_hache(self):
        assert "--require-hashes" in self.dockerfile
        assert "base.lock.txt" in self.dockerfile

    def test_le_code_est_copie_jamais_monte(self):
        assert re.search(r"^COPY --chown=10001:10001 \. /app", self.dockerfile, re.M)


class TestFrontendImage:
    dockerfile = property(lambda self: read(ROOT / "frontend" / "Dockerfile"))

    def test_multi_etages_et_non_root(self):
        content = self.dockerfile
        assert "AS builder" in content and "AS runtime" in content
        assert "USER 101" in content.rstrip().split("EXPOSE")[0]

    def test_nginx_durci(self):
        conf = read(ROOT / "frontend" / "docker" / "nginx.conf")
        for header in ("X-Content-Type-Options", "X-Frame-Options",
                       "Referrer-Policy", "Strict-Transport-Security"):
            assert header in conf
        assert "immutable" in conf, "Les actifs hachés doivent être en cache immuable"
        assert "gzip on" in conf


# ------------------------------------------------------------ docker-compose
class TestComposeStack:
    @pytest.fixture(scope="class")
    def compose(self):
        return yaml.safe_load(read(ROOT / "docker-compose.yml"))

    def test_tous_les_services_requis(self, compose):
        attendus = {"api", "worker", "beat", "postgres", "redis",
                    "minio", "mailhog", "frontend"}
        assert attendus <= set(compose["services"])

    def test_images_epinglees(self, compose):
        for name, svc in compose["services"].items():
            image = svc.get("image")
            if image is None:
                continue
            assert ":" in image, f"{name} : image non épinglée ({image})"
            assert not image.endswith(":latest"), f"{name} : tag latest interdit"

    def test_versions_de_production(self, compose):
        assert compose["services"]["postgres"]["image"].startswith("postgres:16.")
        assert compose["services"]["redis"]["image"].startswith("redis:7.")

    def test_volumes_nommes_pour_les_donnees(self, compose):
        # Piège explicite du J0 : un volume anonyme perd le jeu de données.
        assert "kalyce-postgres-data" in compose["volumes"]
        assert any(v.startswith("kalyce-postgres-data:")
                   for v in compose["services"]["postgres"]["volumes"])

    def test_reseau_interne_dedie(self, compose):
        assert "kalyce-net" in compose["networks"]
        assert compose["services"]["api"]["networks"] == ["kalyce-net"]

    def test_aucun_secret_en_clair(self, compose):
        brut = read(ROOT / "docker-compose.yml")
        for motif in ("SECRET_KEY: \"", "PASSWORD: \"sk", "-----BEGIN"):
            assert motif not in brut

    def test_les_secrets_sont_obligatoires(self, compose):
        brut = read(ROOT / "docker-compose.yml")
        for nom in ("DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY",
                    "HSZ_SIGNING_KEY", "AUDIT_SIGNING_KEY", "OTP_SALT_KEY"):
            assert f"${{{nom}:?" in brut, f"{nom} doit faire échouer le démarrage s'il manque"

    def test_dependances_sur_etat_sain(self, compose):
        api = compose["services"]["api"]["depends_on"]
        assert api["postgres"]["condition"] == "service_healthy"
        assert api["redis"]["condition"] == "service_healthy"


# ------------------------------------------------------------------ Makefile
class TestMakefile:
    def test_cibles_obligatoires(self):
        contenu = read(ROOT / "Makefile")
        for cible in ("up", "down", "test", "lint", "migrate", "seed", "e2e",
                      "secrets", "security", "typecheck", "ci"):
            assert re.search(rf"^{cible}:", contenu, re.M), f"Cible make manquante : {cible}"

    def test_toutes_les_cibles_sont_documentees(self):
        contenu = read(ROOT / "Makefile")
        for ligne in contenu.splitlines():
            match = re.match(r"^([a-z][a-z-]+):", ligne)
            if match and match.group(1) not in {"help"}:
                assert "##" in ligne, f"Cible non documentée : {match.group(1)}"


# --------------------------------------------------------------- Dépendances
class TestDependances:
    def test_locks_haches_presents(self):
        for nom in ("base", "dev", "test"):
            lock = read(BACKEND / "requirements" / f"{nom}.lock.txt")
            assert "--hash=sha256:" in lock, f"{nom}.lock.txt sans empreinte"

    def test_socle_complet_et_epingle(self):
        base = read(BACKEND / "requirements" / "base.txt")
        for paquet in ("Django==", "djangorestframework==", "channels==", "celery==",
                       "psycopg[binary]==", "argon2-cffi==", "webauthn==",
                       "django-axes==", "structlog==", "prometheus-client==",
                       "sentry-sdk==", "drf-spectacular==", "cryptography=="):
            assert paquet in base, f"Dépendance absente du socle : {paquet}"

    def test_aucune_version_flottante(self):
        for nom in ("base", "dev", "test"):
            for ligne in read(BACKEND / "requirements" / f"{nom}.txt").splitlines():
                ligne = ligne.strip()
                if not ligne or ligne.startswith(("#", "-r")):
                    continue
                assert "==" in ligne, f"Version flottante dans {nom}.txt : {ligne}"


# ------------------------------------------------------------ .env.example
class TestEnvExample:
    def test_couvre_toutes_les_variables_obligatoires(self):
        from config.settings.guards import REQUIRED_SECRETS

        contenu = read(ROOT / ".env.example")
        for nom in REQUIRED_SECRETS:
            assert re.search(rf"^{nom}=", contenu, re.M), f"{nom} absent de .env.example"

    def test_documente_le_caractere_obligatoire(self):
        contenu = read(ROOT / ".env.example")
        assert contenu.count("PROD: OBLIGATOIRE") >= 10

    def test_ne_contient_aucun_secret_reel(self):
        contenu = read(ROOT / ".env.example")
        assert "-----BEGIN" not in contenu
        for ligne in contenu.splitlines():
            if ligne.startswith(("DJANGO_SECRET_KEY=", "FIELD_ENCRYPTION_KEY=",
                                 "HSZ_SIGNING_KEY=", "AUDIT_SIGNING_KEY=",
                                 "OTP_SALT_KEY=", "METRICS_TOKEN=")):
                assert ligne.split("=", 1)[1].split()[0] == "replace-me-run-make-secrets"


# -------------------------------------------------------- Hygiène du dépôt
class TestHygieneDuDepot:
    def test_env_est_ignore(self):
        gitignore = read(ROOT / ".gitignore")
        assert re.search(r"^\.env$", gitignore, re.M)
        assert re.search(r"^!\.env\.example$", gitignore, re.M)

    def test_pre_commit_couvre_les_controles_exiges(self):
        config = yaml.safe_load(read(ROOT / ".pre-commit-config.yaml"))
        hooks = {h["id"] for repo in config["repos"] for h in repo["hooks"]}
        for requis in {"ruff", "ruff-format", "mypy", "bandit", "detect-secrets",
                       "check-merge-conflict", "end-of-file-fixer", "eslint", "prettier"}:
            assert requis in hooks, f"Hook pre-commit manquant : {requis}"

    def test_adr_au_moins_huit(self):
        adrs = sorted((ROOT / "docs" / "adr").glob("0*.md"))
        assert len(adrs) >= 8, "Le J0 exige au moins 8 ADR fusionnées"
        for adr in adrs:
            texte = adr.read_text(encoding="utf-8")
            for section in ("## Contexte", "## Décision", "## Conséquences",
                            "## Alternatives écartées"):
                assert section in texte, f"{adr.name} : section {section} manquante"

    def test_contributing_present(self):
        texte = read(ROOT / "CONTRIBUTING.md")
        for attendu in ("Conventional Commits", "quatre yeux", "Definition of Done"):
            assert attendu in texte

    def test_scripts_executables(self):
        for script in ("gen_dev_secrets.sh", "wait_for_health.sh"):
            chemin = ROOT / "scripts" / script
            assert chemin.exists(), f"Script manquant : {script}"
            assert chemin.stat().st_mode & 0o111, f"{script} n'est pas exécutable"

    def test_les_caches_doutils_sont_ignores(self):
        gitignore = read(ROOT / ".gitignore")
        for motif in (".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__"):
            assert motif in gitignore, f"{motif} doit être ignoré (make clean)"
