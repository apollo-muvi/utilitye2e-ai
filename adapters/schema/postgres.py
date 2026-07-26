"""PostgreSQL schema adapter."""

from typing import List
from .base import SchemaAdapter, ColumnInfo


class PostgresAdapter(SchemaAdapter):
    def __init__(self, connection: str):
        self.connection = connection
        self._conn = None

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            import psycopg2
            self._conn = psycopg2.connect(self.connection)
        return self._conn

    def get_tables(self) -> List[str]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            return [r[0] for r in cur.fetchall()]

    def get_columns(self, table: str) -> List[ColumnInfo]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.attname, format_type(a.atttypid, a.atttypmod),
                       a.attnotnull, COALESCE(pk.contype = 'p', false),
                       pg_get_expr(d.adbin, d.adrelid), col_description(a.attrelid, a.attnum)
                FROM pg_attribute a
                LEFT JOIN pg_constraint pk ON pk.conrelid = a.attrelid AND a.attnum = ANY(pk.conkey)
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum
            """, (table,))
            return [
                ColumnInfo(
                    name=r[0], data_type=r[1],
                    nullable=not r[2], is_pk=r[3],
                    default=r[4], comment=r[5] or ""
                )
                for r in cur.fetchall()
            ]
