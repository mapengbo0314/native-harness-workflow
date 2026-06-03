"""Tests for data_table module."""
from src.data_table import DataTable, Column


COLUMNS = [Column("name", "Name"), Column("role", "Role"), Column("age", "Age")]
ROWS = [
    {"name": "Alice", "role": "admin", "age": 30},
    {"name": "Bob", "role": "user", "age": 25},
    {"name": "Carol", "role": "user", "age": 35},
]


def make_table() -> DataTable:
    t = DataTable(columns=COLUMNS)
    for row in ROWS:
        t.add_row(row)
    return t


def test_filter():
    t = make_table().filter("user")
    assert len(t.rows) == 2


def test_sort_ascending():
    t = make_table().sort("age")
    assert t.rows[0]["name"] == "Bob"


def test_export_csv_returns_string():
    t = make_table()
    csv = t.export_csv()
    assert isinstance(csv, str)
    assert "Alice" in csv
    assert "name,role,age" in csv.lower() or "Name,Role,Age" in csv
