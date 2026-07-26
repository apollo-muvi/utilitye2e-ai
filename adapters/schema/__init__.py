"""Schema adapter factory."""

from .base import SchemaAdapter
from .postgres import PostgresAdapter
from .sqlite import SqliteAdapter
from .manual import ManualAdapter


def create_schema_adapter(config: dict) -> SchemaAdapter:
    """Create a schema adapter from config dict.

    Expected config keys:
        adapter: postgres | sqlite | manual
        connection: (for postgres)
        path: (for sqlite / manual)
    """
    adapter_type = config.get("adapter", "manual").lower()

    if adapter_type == "postgres":
        return PostgresAdapter(config["connection"])
    elif adapter_type == "sqlite":
        return SqliteAdapter(config["path"])
    elif adapter_type == "manual":
        return ManualAdapter(config.get("path", "schema.json"))
    else:
        raise ValueError(f"Unknown schema adapter: {adapter_type}")
