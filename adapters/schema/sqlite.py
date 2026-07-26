"""SQLite schema adapter."""

from typing import List
from .base import SchemaAdapter, ColumnInfo


class SqliteAdapter(SchemaAdapter):
    def __init__(self, path: str):
        self.path = path

    def _get_conn(self):
        import sqlite3
        return sqlite3.connect(self.path)

    def get_tables(self) -> List[str]:
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    def get_columns(self, table: str) -> List[ColumnInfo]:
        conn = self._get_conn()
        try:
            cur = conn.execute(f"PRAGMA table_info('{table}')")
            cols = []
            for r in cur.fetchall():
                # cid, name, type, notnull, default, pk
                cols.append(ColumnInfo(
                    name=r[1], data_type=r[2] or "text",
                    nullable=not r[3], is_pk=(r[5] > 0),
                    default=r[4], comment=""
                ))
            return cols
        finally:
            conn.close()
