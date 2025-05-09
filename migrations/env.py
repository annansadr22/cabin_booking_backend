import sys
import os
from logging.config import fileConfig

# Set the correct path for the app module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models here
from app.models import Base, User, Cabin, Booking  # Make sure the path is correct

# Load the Alembic configuration
config = context.config

# Load environment variables (like DATABASE_URL)
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set.")

# Set the database URL dynamically
config.set_main_option("sqlalchemy.url", database_url)

# Setup logging
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
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
