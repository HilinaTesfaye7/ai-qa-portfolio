"""SQL data-quality checks. Each returns a list of problem rows; empty means pass."""


def duplicate_documents(con):
    """Same file content uploaded more than once for a deal."""
    return con.execute("""
        SELECT deal_id, sha256, COUNT(*) AS copies
        FROM documents
        GROUP BY deal_id, sha256
        HAVING COUNT(*) > 1
    """).fetchall()


def orphaned_revenue_lines(con):
    """Revenue lines whose deal doesn't exist (referential integrity)."""
    return con.execute("""
        SELECT r.id, r.deal_id
        FROM revenue_lines r
        LEFT JOIN deals d ON d.id = r.deal_id
        WHERE d.id IS NULL
    """).fetchall()


def unreconciled_totals(con, tolerance=0.01):
    """Deals whose reported revenue doesn't equal the sum of their lines."""
    return con.execute("""
        SELECT d.id, d.reported_revenue, COALESCE(SUM(r.amount), 0) AS line_total
        FROM deals d
        LEFT JOIN revenue_lines r ON r.deal_id = d.id
        GROUP BY d.id
        HAVING ABS(d.reported_revenue - COALESCE(SUM(r.amount), 0)) > ?
    """, (tolerance,)).fetchall()


def deals_missing_documents(con):
    """Deals with no documents at all: a data room that looks complete but isn't."""
    return con.execute("""
        SELECT d.id, d.target_name
        FROM deals d
        LEFT JOIN documents doc ON doc.deal_id = d.id
        WHERE doc.id IS NULL
    """).fetchall()
