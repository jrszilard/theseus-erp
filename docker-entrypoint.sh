#!/bin/sh
set -e

if [ -n "$THESEUS_SEED_PACKS" ]; then
  echo "[entrypoint] seeding packs: $THESEUS_SEED_PACKS"
  python -m theseus.cli seed --packs "$THESEUS_SEED_PACKS"
fi

exec "$@"
