# Contributing to Theseus ERP

## Changing the schema

All schema changes go through Alembic migrations. The workflow:

1. **Edit** the Blueprint YAML (or an ORM model) — make the change you want.

2. **Generate a migration** against a disposable database already at head:
   ```sh
   DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost/<disposable_db> \
     .venv/bin/alembic revision --autogenerate -m "describe the change"
   ```
   Autogenerate compares the ORM model against the live schema and writes a file under
   `alembic/versions/`. The database must already be at `head` so only the delta is
   captured (not the full schema again).

3. **Review the generated file.** Autogenerate is a starting point, not the final word —
   check for:
   - Column types that differ from what you intended
   - Missing server defaults or `nullable` flags
   - Renames detected as drop + add (losing data) instead of `op.alter_column`
   - Any `op.drop_*` statements you did not expect

4. **Run the drift gate** (disposable sync URL only — never prod):
   ```sh
   python -m theseus.cli check-migrations --url postgresql://<user>:<pass>@localhost/<disposable_db>
   ```
   Must print: `[check-migrations] OK: migrations match the declared schema`

5. **Commit.** Deploy runs `theseus migrate` (`alembic upgrade head`), altering prod in
   place with data preserved.
