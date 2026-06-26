from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import theseus.keel.assets.models
import theseus.keel.auth.models

# Import static ORM models so their tables are in Base.metadata for autogenerate.
import theseus.keel.event_store.models
import theseus.keel.knowledge_graph.models
import theseus.shipwright.conversation.models  # noqa: F401
from theseus.bootstrap import build_registry, register_blueprint_tables
from theseus.config import settings
from theseus.database import Base

config = context.config

# Respect a url already set on the config (e.g. by `theseus check-migrations`);
# otherwise use the project's SYNC url (psycopg2). Never the async (+asyncpg) url.
config.set_main_option(
    "sqlalchemy.url",
    config.get_main_option("sqlalchemy.url") or settings.database_url_sync,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Populate Base.metadata with the dynamically-generated Blueprint tables, so
# autogenerate/check see the FULL schema — not just the static ORM models.
register_blueprint_tables(build_registry())
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
