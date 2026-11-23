"""Maintenance helpers shared by the database converters.

Usage:
    python db_tools.py number-compounds DATABASE.db [...]

number-compounds adds (or refreshes) metadata_NumberCompounds: how many compounds each glass has
with a value above 0. "Unspecified" (unnamed residuals in SciGlass) is not counted, and glasses
with no composition get NULL rather than 0.
"""

import sqlite3
import sys

NOT_COUNTED = {"Unspecified"}
COLUMN = "metadata_NumberCompounds"


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def compound_counts(conn: sqlite3.Connection) -> dict:
    """{row_id: number of compounds above 0, or None when the glass has no composition}."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(compounds)") if r[1].startswith("compounds_")]
    counted = [c for c in cols if c[len("compounds_"):] not in NOT_COUNTED]
    counts = {}
    for row_id, *values in conn.execute(f"SELECT row_id, {', '.join(quote(c) for c in counted)} FROM compounds"):
        n = sum(1 for v in values if v is not None and v != 0)
        counts[row_id] = n or None
    return counts


def add_number_compounds(conn: sqlite3.Connection) -> int:
    """Add or refresh metadata_NumberCompounds. Returns how many glasses got a count."""
    existing = [r[1] for r in conn.execute("PRAGMA table_info(metadata)")]
    if COLUMN not in existing:
        conn.execute(f"ALTER TABLE metadata ADD COLUMN {COLUMN} INTEGER")
    counts = compound_counts(conn)
    conn.executemany(f"UPDATE metadata SET {COLUMN} = ? WHERE row_id = ?", ((n, rid) for rid, n in counts.items()))
    conn.commit()
    return sum(1 for n in counts.values() if n)


def check_number_compounds(conn: sqlite3.Connection) -> list:
    """Problems (as text) where metadata_NumberCompounds disagrees with the compounds table."""
    expected = compound_counts(conn)
    problems = []
    stored = dict(conn.execute(f"SELECT row_id, {COLUMN} FROM metadata"))
    for rid, n in expected.items():
        if stored.get(rid) != n:
            problems.append(f"NumberCompounds for {rid}: stored {stored.get(rid)!r}, expected {n!r}")
    return problems


def main(argv) -> int:
    if len(argv) < 2 or argv[0] != "number-compounds":
        print(__doc__)
        return 2
    for path in argv[1:]:
        conn = sqlite3.connect(path)
        n = add_number_compounds(conn)
        problems = check_number_compounds(conn)
        conn.close()
        print(f"{path}: NumberCompounds set for {n} glasses" + (f"; {len(problems)} problems" if problems else ""))
        if problems:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
