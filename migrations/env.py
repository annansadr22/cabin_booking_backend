import sys
import os
from logging.config import fileConfig

# Set the correct path for the app module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import engine_from_config, pool
from alembic import context
from app.database import Base, engine  # Your app modules
from app.models import User, Cabin, Booking  # Your models


config = context.config
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

def run_migrations_online():
    connectable = engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
