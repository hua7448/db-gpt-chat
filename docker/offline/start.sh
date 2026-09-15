#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
DEPLOY_DIR="$(pwd)"
test -s site.env || { echo 'Configure site.env from site.env.example first'; exit 1; }
docker image inspect k-ics:20260909 >/dev/null
docker image inspect k-ics-python:20260909 >/dev/null
mkdir -p data/pilot data/logs certs
if [ ! -f data/pilot/meta_data/alembic.ini ]; then
  INIT_ID=$(docker create k-ics:20260909)
  trap 'docker rm "$INIT_ID" >/dev/null' EXIT
  docker cp "$INIT_ID:/app/pilot/." data/pilot/
  docker rm "$INIT_ID" >/dev/null
  trap - EXIT
fi
docker run -d --name k-ics --restart unless-stopped \
  --env-file site.env -e KICS_HOST_PILOT="$DEPLOY_DIR/data/pilot" \
  -p "${KICS_BIND_ADDRESS:-127.0.0.1}:${KICS_PORT:-5670}:5670" \
  -v "$DEPLOY_DIR/data/pilot:/app/pilot" \
  -v "$DEPLOY_DIR/data/logs:/app/logs" \
  -v "$DEPLOY_DIR/site.toml:/app/docker/offline/site.toml:ro" \
  -v "$DEPLOY_DIR/certs:/app/certs:ro" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  k-ics:20260909
