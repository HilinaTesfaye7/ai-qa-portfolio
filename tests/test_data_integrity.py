"""SQL data-quality checks.

Each check runs twice: on clean data it must find nothing, and on data with
planted defects it must find exactly those defects. The second half proves the
check actually works instead of passing silently.
"""
from app import data_checks as dc


def test_row_counts(clean_db):
    counts = {t: clean_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("deals", "revenue_lines", "documents")}
    assert counts == {"deals": 3, "revenue_lines": 7, "documents": 4}


def test_clean_data_passes_all_checks(clean_db):
    assert dc.duplicate_documents(clean_db) == []
    assert dc.orphaned_revenue_lines(clean_db) == []
    assert dc.unreconciled_totals(clean_db) == []
    assert dc.deals_missing_documents(clean_db) == []


def test_detects_duplicate_upload(dirty_db):
    assert dc.duplicate_documents(dirty_db) == [(2, "c9d4", 2)]


def test_detects_orphaned_record(dirty_db):
    assert dc.orphaned_revenue_lines(dirty_db) == [(8, 99)]


def test_detects_totals_that_do_not_reconcile(dirty_db):
    rows = dc.unreconciled_totals(dirty_db)
    assert [r[0] for r in rows] == [1]
    deal_id, reported, line_total = rows[0]
    assert reported - line_total == 10_000


def test_detects_data_room_that_looks_complete_but_is_not(clean_db):
    clean_db.execute("INSERT INTO deals VALUES (4, 'Empty Room Co', 0)")
    try:
        assert dc.deals_missing_documents(clean_db) == [(4, "Empty Room Co")]
    finally:
        clean_db.rollback()
