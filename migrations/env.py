"""Alembic environment (database.md, tasks.md T4.3)."""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from jobhunt_core.storage.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Every model module is imported by jobhunt_core.storage.models
# (see that package's __init__.py), so Base.metadata already reflects
# every table -- required for --autogenerate to see new/changed models.
target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the SQLite URL the same way Settings resolves data_dir.

    Not hardcoded in alembic.ini (which is committed) so this doesn't
    bake a machine-specific absolute path into version control;
    JOBHUNT_DATA_DIR (config.md) overrides it the same way it would
    for the running application.
    """
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = Path(os.environ.get("JOBHUNT_DATA_DIR", repo_root / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'jobhunt.db'}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
