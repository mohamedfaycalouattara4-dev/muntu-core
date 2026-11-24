# =============================================================================
# KALYCE · Interface unique de développement (ADR-0004)
# Une seule façon de faire chaque chose — identique en local et en CI.
# =============================================================================
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE ?= docker compose
BACKEND := backend
FRONTEND := frontend
PY ?= python3
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
API_URL ?= http://localhost:8000

.PHONY: help up down stop logs ps build rebuild secrets env migrate makemigrations \
        seed shell test test-backend test-frontend cov lint fmt typecheck security \
        audit e2e openapi smoke clean nuke venv install hooks ci

help: ## Affiche cette aide
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------- Environnement
env: ## Crée .env depuis .env.example s'il n'existe pas
	@test -f .env || (cp .env.example .env && echo "→ .env créé depuis .env.example")

secrets: env ## Génère des secrets de développement locaux dans .env (jamais versionnés)
	@./scripts/gen_dev_secrets.sh

up: secrets ## Démarre toute la plateforme (make up = une seule commande, R11)
	$(COMPOSE) up -d --build
	@./scripts/wait_for_health.sh $(API_URL)/health 180

down: ## Arrête la plateforme (les volumes nommés sont conservés)
	$(COMPOSE) down

stop: ## Arrête les conteneurs sans les supprimer
	$(COMPOSE) stop

nuke: ## Arrête ET supprime les volumes (destructif, jeu de données perdu)
	$(COMPOSE) down -v

ps: ## État des services
	$(COMPOSE) ps

logs: ## Journaux agrégés (make logs S=api pour un service)
	$(COMPOSE) logs -f $(S)

build: ## Construit les images
	$(COMPOSE) build

rebuild: ## Reconstruit sans cache
	$(COMPOSE) build --no-cache

# ----------------------------------------------------------------- Base de données
migrate: ## Applique les migrations
	$(COMPOSE) run --rm -e KALYCE_RUN_MIGRATIONS=false api python manage.py migrate --noinput

makemigrations: ## Génère les migrations manquantes
	$(COMPOSE) run --rm -e KALYCE_RUN_MIGRATIONS=false api python manage.py makemigrations

seed: ## Charge le jeu de données de démonstration (3 vendeurs, 2 livreurs, 1 live, 20 produits, 50 commandes)
	$(COMPOSE) run --rm -e KALYCE_RUN_MIGRATIONS=false api python manage.py seed_demo --reset --scale full

shell: ## Shell Django dans le conteneur api
	$(COMPOSE) run --rm -e KALYCE_RUN_MIGRATIONS=false api python manage.py shell

# ----------------------------------------------------------------- Environnement local (sans Docker)
venv: ## Crée le virtualenv local
	test -d $(VENV) || $(PY) -m venv $(VENV)

install: venv ## Installe les dépendances de développement et de test
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r $(BACKEND)/requirements/test.txt

hooks: install ## Installe les hooks pre-commit
	$(VENV)/bin/pre-commit install --install-hooks
	$(VENV)/bin/pre-commit install --hook-type commit-msg

# ----------------------------------------------------------------- Qualité
test: test-backend test-frontend ## Toute la suite de tests

test-backend: ## Tests backend (pytest)
	cd $(BACKEND) && ../$(VENV_PY) -m pytest -q

cov: ## Tests backend avec couverture
	cd $(BACKEND) && ../$(VENV_PY) -m pytest -q --cov=apps --cov=config \
	 --cov-report=term-missing --cov-report=xml

test-frontend: ## Tests frontend (vitest)
	cd $(FRONTEND) && npm run test --if-present

lint: ## Lint backend (ruff) et frontend (eslint)
	$(VENV)/bin/ruff check $(BACKEND)
	$(VENV)/bin/ruff format --check $(BACKEND)
	cd $(FRONTEND) && npm run lint --if-present

fmt: ## Formate le code
	$(VENV)/bin/ruff check --fix $(BACKEND)
	$(VENV)/bin/ruff format $(BACKEND)

typecheck: ## Vérification de types (mypy, strict progressif)
	cd $(BACKEND) && ../$(VENV)/bin/mypy .

security: ## Analyse statique de sécurité (bandit + detect-secrets)
	$(VENV)/bin/bandit -q -c $(BACKEND)/pyproject.toml -r $(BACKEND)/apps $(BACKEND)/config
	$(VENV)/bin/detect-secrets scan --baseline .secrets.baseline

audit: ## Vulnérabilités connues des dépendances
	$(VENV)/bin/pip-audit -r $(BACKEND)/requirements/base.txt

e2e: ## Tests end-to-end Playwright contre la plateforme démarrée
	cd $(FRONTEND) && npx playwright test

openapi: ## Génère le schéma OpenAPI
	$(COMPOSE) run --rm -e KALYCE_RUN_MIGRATIONS=false api python manage.py spectacular --file openapi.yaml

smoke: ## Vérifie que /health répond 200
	./scripts/wait_for_health.sh $(API_URL)/health 60

ci: lint test-backend security ## Exactement ce que la CI exécute

clean: ## Supprime les artefacts locaux
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache \
	       $(BACKEND)/htmlcov $(BACKEND)/.coverage $(BACKEND)/coverage.xml
