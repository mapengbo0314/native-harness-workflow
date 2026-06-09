"""Data table module — filterable, sortable table of records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Column:
    key: str
    label: str
    sortable: bool = True


@dataclass
class DataTable:
    columns: list[Column]
    rows: list[dict[str, Any]] = field(default_factory=list)
    _sort_key: str | None = None
    _filter: str = ""

    def add_row(self, row: dict[str, Any]) -> None:
        self.rows.append(row)

    def filter(self, query: str) -> "DataTable":
        """Return a filtered view matching query against all string values."""
        filtered = [
            r for r in self.rows
            if any(query.lower() in str(v).lower() for v in r.values())
        ]
        result = DataTable(columns=self.columns, rows=filtered)
        result._filter = query
        return result

    def sort(self, key: str, ascending: bool = True) -> "DataTable":
        sorted_rows = sorted(self.rows, key=lambda r: r.get(key, ""), reverse=not ascending)
        result = DataTable(columns=self.columns, rows=sorted_rows)
        result._sort_key = key
        return result

    def to_dict_list(self) -> list[dict[str, Any]]:
        return list(self.rows)

    # TODO: implement export_csv() — should return CSV string of current view
