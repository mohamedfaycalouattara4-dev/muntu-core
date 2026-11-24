#!/usr/bin/env bash
# Attend qu'une URL réponde 200. Échec bruyant après le délai (R7).
set -euo pipefail
URL="${1:?usage: wait_for_health.sh URL [TIMEOUT_SECONDS]}"
TIMEOUT="${2:-120}"
start=$(date +%s)
until curl -fsS -o /dev/null "$URL"; do
  now=$(date +%s)
  if (( now - start > TIMEOUT )); then
    echo "✗ $URL n'a pas répondu 200 en ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 2
done
echo "✓ $URL répond 200 en $(( $(date +%s) - start ))s"
