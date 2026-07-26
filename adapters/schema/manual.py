"""
Manual schema adapter — read from a JSON file.

Use this when you don't want to connect to a live database.
Just provide a schema.json file.

Example schema.json:
{
  "tables": {
    "parents": [
      {"name": "id", "data_type": "uuid", "nullable": false, "is_pk": true},
      {"name": "name", "data_type": "varchar", "nullable": false},
      {"name": "phone", "data_type": "varchar"}
    ],
    "students": [...]
  }
}
"""

import json
from typing import List
from .base import SchemaAdapter, ColumnInfo


class ManualAdapter(SchemaAdapter):
    def __init__(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def get_tables(self) -> List[str]:
        return list(self.schema.get("tables", {}).keys())

    def get_columns(self, table: str) -> List[ColumnInfo]:
        cols = self.schema.get("tables", {}).get(table, [])
        return [
            ColumnInfo(
                name=c["name"],
                data_type=c.get("data_type", "text"),
                nullable=c.get("nullable", True),
                is_pk=c.get("is_pk", False),
                default=c.get("default"),
                comment=c.get("comment", ""),
            )
            for c in cols
        ]
