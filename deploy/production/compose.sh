#!/bin/sh
# No default environment file; no local .env is loaded.
set -eu
: "${RISKBEX_PROD_ENV:?Set RISKBEX_PROD_ENV to an absolute production env file}"
case "$RISKBEX_PROD_ENV" in /*) ;; *) echo 'Production env path must be absolute' >&2; exit 2;; esac
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec docker compose --project-directory "$root" --project-name riskbex-prod \
    --env-file "$RISKBEX_PROD_ENV" -f "$root/docker-compose.yml" \
    -f "$root/deploy/production/compose.yaml" "$@"
