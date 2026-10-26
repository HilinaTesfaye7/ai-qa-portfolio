"""Builds a small SQLite database of acquisition deals.

`build(path, dirty=False)` creates clean data. `dirty=True` plants the kinds of
defects the data checks must catch: a duplicate upload, an orphaned record and
a total that doesn't reconcile.
"""
import sqlite3
import sys

SCHEMA = """
CREATE TABLE deals (
    id INTEGER PRIMARY KEY,
    target_name TEXT NOT NULL,
    reported_revenue REAL NOT NULL
);
CREATE TABLE revenue_lines (
    id INTEGER PRIMARY KEY,
    deal_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    amount REAL NOT NULL
);
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    deal_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
"""

DEALS = [
    (1, "Northwind Clinics", 1_200_000.0),
    (2, "Blue Harbor Dental", 845_000.0),
    (3, "Summit Physio Group", 2_310_000.0),
]

REVENUE_LINES = [
    (1, 1, "2025-Q1", 290_000.0), (2, 1, "2025-Q2", 300_000.0),
    (3, 1, "2025-Q3", 305_000.0), (4, 1, "2025-Q4", 305_000.0),
    (5, 2, "2025-H1", 410_000.0), (6, 2, "2025-H2", 435_000.0),
    (7, 3, "2025-FY", 2_310_000.0),
]

DOCUMENTS = [
    (1, 1, "northwind_pl_2025.pdf", "a1f3"),
    (2, 1, "northwind_balance_sheet.pdf", "b7c2"),
    (3, 2, "blueharbor_pl_2025.pdf", "c9d4"),
    (4, 3, "summit_audited_fs.pdf", "d2e8"),
]


def build(path, dirty=False):
    con = sqlite3.connect(path)
    con.executescript("DROP TABLE IF EXISTS deals; DROP TABLE IF EXISTS revenue_lines; DROP TABLE IF EXISTS documents;")
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO deals VALUES (?,?,?)", DEALS)
    con.executemany("INSERT INTO revenue_lines VALUES (?,?,?,?)", REVENUE_LINES)
    con.executemany("INSERT INTO documents VALUES (?,?,?,?)", DOCUMENTS)
    if dirty:
        # Same file uploaded twice to the data room.
        con.execute("INSERT INTO documents VALUES (5, 2, 'blueharbor_pl_2025 (1).pdf', 'c9d4')")
        # A revenue line pointing at a deal that doesn't exist.
        con.execute("INSERT INTO revenue_lines VALUES (8, 99, '2025-Q1', 50000.0)")
        # Lines no longer add up to the reported total.
        con.execute("UPDATE revenue_lines SET amount = 295000.0 WHERE id = 4")
    con.commit()
    con.close()


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "data/deals.db")
