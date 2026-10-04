import sqlite3, time
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "sample.db"


def init_db():
    if DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    con.executescript((BASE / "schema.sql").read_text())
    con.commit()
    con.close()


def _con():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def get_schema() -> dict[str, list[str]]:
    con = _con()
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = {t: [r[1] for r in con.execute(f"PRAGMA table_info({t})")] for t in names}
    con.close()
    return out


def get_fks() -> set:
    """Each FK as frozenset({(table, col), (ref_table, ref_col)}), lowercased."""
    con, fks = _con(), set()
    for t in get_schema():
        for r in con.execute(f"PRAGMA foreign_key_list({t})"):
            fks.add(frozenset({(t.lower(), r[3].lower()), (r[2].lower(), r[4].lower())}))
    con.close()
    return fks


def schema_text() -> str:
    """Schema for the prompt: columns, foreign keys, and value hints for text columns (so the model
    filters on real values like 'California' instead of guessing 'CA')."""
    con, lines = _con(), []
    for t in get_schema():
        info = list(con.execute(f"PRAGMA table_info({t})"))
        lines.append(f"{t}(" + ", ".join(f"{r[1]} {r[2]}{' PK' if r[5] else ''}" for r in info) + ")")
        for r in con.execute(f"PRAGMA foreign_key_list({t})"):
            lines.append(f"  FK: {t}.{r[3]} -> {r[2]}.{r[4]}")
        total = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for r in info:
            if (r[2] or "").upper() != "TEXT":
                continue
            vals = [v[0] for v in con.execute(
                f'SELECT DISTINCT "{r[1]}" FROM {t} WHERE "{r[1]}" IS NOT NULL LIMIT 11')]
            if 0 < len(vals) <= 10 and len(vals) < total:  # repeated values = categorical column
                lines.append(f"  values {t}.{r[1]}: " + ", ".join(repr(v) for v in vals))
            elif vals:
                lines.append(f"  examples {t}.{r[1]}: " + ", ".join(repr(v) for v in vals[:3]))
    con.close()
    return "\n".join(lines)


def explain(sql: str):
    con = _con()
    try:
        con.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
    finally:
        con.close()


def run_query(sql: str, limit: int = 100):
    con, start = _con(), time.time()
    con.set_progress_handler(lambda: 1 if time.time() - start > 3 else 0, 10000)
    try:
        cur = con.execute(sql)
        rows = cur.fetchmany(limit)
        return [d[0] for d in cur.description], [list(r) for r in rows]
    finally:
        con.close()
