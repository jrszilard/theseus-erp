#!/usr/bin/env bash
set -euo pipefail

NET=theseus-smoke-net
DB=theseus-smoke-db
APP=theseus-smoke-app
IMG=theseus-smoke:latest

cleanup() {
  docker rm -f "$APP" "$DB" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[smoke] building image…"
docker build -t "$IMG" .

docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" \
  -e POSTGRES_USER=theseus -e POSTGRES_PASSWORD=theseus -e POSTGRES_DB=theseus \
  postgres:16-alpine >/dev/null

echo "[smoke] waiting for postgres…"
pg_ready=""
for _ in $(seq 1 30); do
  docker exec "$DB" pg_isready -U theseus >/dev/null 2>&1 && { pg_ready=1; break; }
  sleep 1
done
[ -n "$pg_ready" ] || { echo "[smoke] FAIL: postgres never became ready"; docker logs "$DB"; exit 1; }

docker run -d --name "$APP" --network "$NET" -p 8001:8000 \
  -e DATABASE_URL=postgresql+asyncpg://theseus:theseus@$DB:5432/theseus \
  -e STORAGE_BACKEND=local \
  "$IMG" >/dev/null

echo "[smoke] waiting for app…"
ok=""
for _ in $(seq 1 30); do
  if curl -fs http://localhost:8001/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ -n "$ok" ] || { echo "[smoke] FAIL: /health never came up"; docker logs "$APP"; exit 1; }

echo "[smoke] checking board HTML…"
curl -fs http://localhost:8001/ | grep -q "Ideas" || { echo "[smoke] FAIL: board missing"; exit 1; }

echo "[smoke] PASS"
