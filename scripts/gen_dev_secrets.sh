#!/usr/bin/env bash
# Génère des secrets de DÉVELOPPEMENT dans .env (ADR-0008).
# Aucun secret réel n'entre jamais dans le dépôt : .env est gitignoré.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=".env"
[[ -f "$ENV_FILE" ]] || cp .env.example "$ENV_FILE"

rand_hex() { openssl rand -hex "$1"; }
rand_b64() { openssl rand -base64 32 | tr -d '\n'; }

set_var() {  # set_var NOM VALEUR — n'écrase jamais une valeur déjà réelle
  local name="$1" value="$2" current
  current="$(grep -E "^${name}=" "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
  if [[ -z "$current" || "$current" == replace-* || "$current" == "CHANGE_ME" ]]; then
    if grep -qE "^${name}=" "$ENV_FILE"; then
      python3 - "$ENV_FILE" "$name" "$value" <<'PY'
import sys, pathlib
path, name, value = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
lines = p.read_text().splitlines()
p.write_text("\n".join(f"{name}={value}" if l.startswith(f"{name}=") else l for l in lines) + "\n")
PY
    else
      printf '%s=%s\n' "$name" "$value" >> "$ENV_FILE"
    fi
    echo "→ ${name} généré"
  fi
}

set_var DJANGO_SECRET_KEY "$(rand_hex 32)$(rand_hex 8)"
set_var FIELD_ENCRYPTION_KEY "$(rand_b64)"
set_var HSZ_SIGNING_KEY "$(rand_hex 32)"
set_var AUDIT_SIGNING_KEY "$(rand_hex 32)"
set_var OTP_SALT_KEY "$(rand_hex 32)"
set_var METRICS_TOKEN "$(rand_hex 16)"
echo "Secrets de développement prêts dans .env (non versionné)."
