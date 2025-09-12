"""Alembic migration environment for AI Model Validation Platform."""

import asyncio
import logging
import sys
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add the project root to Python path
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir))

# Import your models and database configuration
from database import DATABASE_URL, Base
from models import *  # This imports all models including AuthUser

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

def get_database_url():
    """Get database URL from environment or config."""
    # Try environment variables first
    db_url = os.getenv('AIVALIDATION_DATABASE_URL') or os.getenv('DATABASE_URL')
    
    if not db_url:
        # Fallback to configured URL
        db_url = DATABASE_URL
    
    if not db_url:
        # Final fallback
        db_url = "sqlite:///./dev_database.db"
    
    logger.info(f"Using database URL: {db_url.replace('password', '***')}")
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # For SQLite compatibility
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Override the sqlalchemy.url in config with our dynamic URL
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,  # For SQLite compatibility
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()