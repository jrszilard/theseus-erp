# Theseus ERP

An open-source, AI-first ERP for small manufacturing and trade businesses.

> Named after the Ship of Theseus — every module can be rebuilt, no two implementations are alike.

## Quick Start

```bash
git clone <repo-url>
cd theseus
docker compose up -d
# Open http://localhost:8000/health
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start database
docker compose up db -d
docker compose exec db psql -U theseus -c "CREATE DATABASE theseus_test;"

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ -v

# Lint and type check
ruff check src/ tests/
mypy src/theseus/ --ignore-missing-imports
```

## Architecture

See `docs/superpowers/specs/2026-04-15-theseus-erp-architecture-design.md` for the full architecture spec.

## License

AGPL-3.0-or-later
