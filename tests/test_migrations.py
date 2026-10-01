from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.models import Base

ROOT = Path(__file__).resolve().parent.parent


def test_migrations_create_exactly_the_model_schema():
    """Running every migration must yield the same tables, columns, indexes and keys as the models."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        differences = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": False}), Base.metadata)
    assert differences == []
