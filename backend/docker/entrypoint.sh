#!/bin/sh
# Point d'entrée unique — échec bruyant, jamais de repli silencieux (R7).
set -eu

: "${DJANGO_SETTINGS_MODULE:?DJANGO_SETTINGS_MODULE est obligatoire}"

if [ "${KALYCE_WAIT_FOR_DB:-true}" = "true" ]; then
  python - <<'PY'
import os, socket, sys, time
host = os.environ.get("DB_HOST", "postgres")
port = int(os.environ.get("DB_PORT", "5432"))
deadline = time.time() + float(os.environ.get("KALYCE_DB_WAIT_SECONDS", "60"))
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"Base de données injoignable: {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
fi

if [ "${KALYCE_RUN_MIGRATIONS:-false}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${KALYCE_COLLECTSTATIC:-false}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
