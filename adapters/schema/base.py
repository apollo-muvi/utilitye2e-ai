"""
SchemaAdapter — abstract base for DB schema introspection.

Implement get_tables() and get_columns() to support a new database.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ColumnInfo:
    """Represents a database column."""
    def __init__(self, name: str, data_type: str, nullable: bool = True,
                 is_pk: bool = False, default: Any = None, comment: str = ""):
        self.name = name
        self.data_type = data_type
        self.nullable = nullable
        self.is_pk = is_pk
        self.default = default
        self.comment = comment

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "nullable": self.nullable,
            "is_pk": self.is_pk,
            "default": self.default,
            "comment": self.comment,
        }

    def __repr__(self):
        return f"ColumnInfo({self.name}: {self.data_type}, pk={self.is_pk})"


class SchemaAdapter(ABC):
    """Abstract schema introspection adapter."""

    @abstractmethod
    def get_tables(self) -> List[str]:
        """Return all table names."""
        ...

    @abstractmethod
    def get_columns(self, table: str) -> List[ColumnInfo]:
        """Return column info for a table."""
        ...

    def get_table_schema(self, table: str) -> Dict[str, Any]:
        """Return full schema dict for a table (for LLM prompt context)."""
        return {
            "table": table,
            "columns": [c.to_dict() for c in self.get_columns(table)],
        }

    def search_tables(self, keyword: str) -> List[str]:
        """Find tables matching a keyword (case-insensitive)."""
        keyword = keyword.lower()
        return [t for t in self.get_tables() if keyword in t.lower()]
