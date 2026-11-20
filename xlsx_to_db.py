"""Convert a SciGlass-style spreadsheet into a SciGlass Explorer database.

Usage:
    python xlsx_to_db.py SciGlass_Plus_properties.xlsx [output.db]
        [--sheet NAME] [--first-property T0] [--first-metadata Authors] [--verify-only]

Expected spreadsheet layout (one row per glass, header in row 1):
    <ID> | element columns (H, Li, ...) | compound columns (SiO2, ...) | property columns (T0, ...) | metadata columns (Authors, ...)

    * The first column is the glass ID (e.g. SGP-1). It becomes row_id in every table.
    * Element columns are the run of periodic-table symbols right after the ID.
    * Compound columns run from there up to the first property column (--first-property, default T0).
    * Property columns run up to the first metadata column (--first-metadata, default Authors).

Database layout (what main.py queries):
    elements(row_id, elements_<symbol>, ...)
    compounds(row_id, compounds_<formula>, ...)
    property(row_id, property_<name>, ...)
    metadata(row_id, metadata_<name>, ...)

Column names are kept exactly as in the spreadsheet. Blank cells become NULL. Element, compound
and property values are stored as REAL numbers; metadata keeps the spreadsheet's own types.

After writing, every cell is read back from the database and compared with the spreadsheet; the
script exits non-zero if anything differs. Use --verify-only to re-check an existing database.
"""

import argparse
import math
import os
import sqlite3
import sys

import openpyxl

ELEMENT_SYMBOLS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y",
    "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce",
    "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir",
    "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm",
    "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc",
    "Lv", "Ts", "Og",
}

NUMERIC_TABLES = ("elements", "compounds", "property")
TABLES = NUMERIC_TABLES + ("metadata",)


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def read_sheet(path: str, sheet: str = None):
    """Return (header, rows) with every cell value exactly as openpyxl reads it."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    header = list(next(rows_iter))
    while header and header[-1] is None:  # trailing empty header cells
        header.pop()
    width = len(header)
    rows = []
    for row in rows_iter:
        row = list(row)
        if any(v is not None for v in row[width:]):
            raise ValueError(f"Spreadsheet row {len(rows) + 2} has data beyond the last header column")
        row = row[:width] + [None] * (width - len(row))
        if all(v is None for v in row):
            continue  # fully blank row
        rows.append(row)
    wb.close()
    return header, rows


def split_columns(header, first_property: str, first_metadata: str) -> dict:
    """Assign each data column (by index) to a table."""
    names = [str(h).strip() if h is not None else "" for h in header]
    for required in (first_property, first_metadata):
        if required not in names:
            raise ValueError(f"Column '{required}' not found in the header")
    ip, im = names.index(first_property), names.index(first_metadata)
    if not 1 < ip < im:
        raise ValueError(f"Expected ID, then elements/compounds, then '{first_property}'..., then '{first_metadata}'...")

    ie = 1
    while ie < ip and names[ie] in ELEMENT_SYMBOLS:
        ie += 1

    groups = {
        "elements": list(range(1, ie)),
        "compounds": list(range(ie, ip)),
        "property": list(range(ip, im)),
        "metadata": list(range(im, len(names))),
    }
    for table, idxs in groups.items():
        seen = set()
        for i in idxs:
            if not names[i]:
                raise ValueError(f"Column {i + 1} has an empty header")
            if names[i] in seen:
                raise ValueError(f"Duplicate column '{names[i]}' in {table}")
            seen.add(names[i])
    return groups


def to_number(value, where: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Non-numeric value {value!r} at {where}")
    return float(value)


def sql_type(values) -> str:
    kinds = {type(v) for v in values if v is not None}
    if kinds <= {int}:
        return "INTEGER"
    if kinds <= {int, float}:
        return "REAL"
    return "TEXT"


def convert(xlsx_path: str, db_path: str, sheet: str, first_property: str, first_metadata: str) -> None:
    print(f"Reading {xlsx_path} ...")
    header, rows = read_sheet(xlsx_path, sheet)
    groups = split_columns(header, first_property, first_metadata)
    names = [str(h).strip() for h in header]

    ids = [r[0] for r in rows]
    if any(i is None for i in ids):
        raise ValueError("Some rows have no ID in the first column")
    if len(set(ids)) != len(ids):
        raise ValueError("Glass IDs in the first column are not unique")

    for table, idxs in groups.items():
        print(f"  {table:9s} {len(idxs):4d} columns" + (f"  ({names[idxs[0]]} ... {names[idxs[-1]]})" if idxs else ""))
    print(f"  {len(rows)} rows")

    tmp_path = db_path + ".tmp"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    conn = sqlite3.connect(tmp_path)
    try:
        for table, idxs in groups.items():
            if table in NUMERIC_TABLES:
                types = ["REAL"] * len(idxs)
                data = [
                    [r[0]] + [to_number(r[i], f"row {n + 2}, column {names[i]}") for i in idxs]
                    for n, r in enumerate(rows)
                ]
            else:
                types = [sql_type(r[i] for r in rows) for i in idxs]
                data = [[r[0]] + [r[i] for i in idxs] for r in rows]

            cols = ", ".join(f"{quote(f'{table}_{names[i]}')} {t}" for i, t in zip(idxs, types))
            conn.execute(f"CREATE TABLE {table} (row_id TEXT PRIMARY KEY, {cols})")
            placeholders = ", ".join("?" * (len(idxs) + 1))
            conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", data)
        conn.commit()
    finally:
        conn.close()
    os.replace(tmp_path, db_path)
    print(f"Wrote {db_path}")


def same(cell, stored) -> bool:
    if cell is None or stored is None:
        return cell is None and stored is None
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        if not isinstance(stored, (int, float)):
            return False
        if math.isnan(cell):
            return math.isnan(stored)
        return float(cell) == float(stored)
    return type(cell) is type(stored) and cell == stored


def verify(xlsx_path: str, db_path: str, sheet: str, first_property: str, first_metadata: str) -> bool:
    print(f"Verifying {db_path} against {xlsx_path} ...")
    header, rows = read_sheet(xlsx_path, sheet)
    groups = split_columns(header, first_property, first_metadata)
    names = [str(h).strip() for h in header]

    conn = sqlite3.connect(db_path)
    problems = []
    cells = 0
    try:
        for table, idxs in groups.items():
            db_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            expected = ["row_id"] + [f"{table}_{names[i]}" for i in idxs]
            if db_cols != expected:
                problems.append(f"{table}: columns differ from the spreadsheet")
                continue
            db_rows = {r[0]: r for r in conn.execute(f"SELECT * FROM {table}")}
            if len(db_rows) != len(rows):
                problems.append(f"{table}: {len(db_rows)} rows in database, {len(rows)} in spreadsheet")
            for n, r in enumerate(rows):
                stored = db_rows.get(r[0])
                if stored is None:
                    problems.append(f"{table}: ID {r[0]} missing")
                    continue
                for k, i in enumerate(idxs, start=1):
                    cells += 1
                    if not same(r[i], stored[k]):
                        problems.append(f"{table}: ID {r[0]}, column {names[i]}: spreadsheet {r[i]!r}, database {stored[k]!r}")
    finally:
        conn.close()

    total_cells = len(rows) * (len(header) - 1)
    if cells != total_cells:
        problems.append(f"compared {cells} cells, expected {total_cells}")
    for p in problems[:50]:
        print("  MISMATCH:", p)
    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        return False
    print(f"OK: all {cells} data cells in {len(rows)} rows match exactly (plus {len(rows)} IDs as row_id).")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx")
    parser.add_argument("db", nargs="?", help="output database (default: next to the spreadsheet, same name, .db)")
    parser.add_argument("--sheet", help="worksheet name (default: first sheet)")
    parser.add_argument("--first-property", default="T0")
    parser.add_argument("--first-metadata", default="Authors")
    parser.add_argument("--verify-only", action="store_true", help="only compare an existing database with the spreadsheet")
    args = parser.parse_args(argv)

    db = args.db or os.path.splitext(args.xlsx)[0] + ".db"
    opts = (args.sheet, args.first_property, args.first_metadata)
    try:
        if not args.verify_only:
            convert(args.xlsx, db, *opts)
        return 0 if verify(args.xlsx, db, *opts) else 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
