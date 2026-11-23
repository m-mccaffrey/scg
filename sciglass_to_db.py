"""Convert the raw SciGlass table export into SciGlass Explorer databases.

Usage:
    python sciglass_to_db.py SCIGLASS_DIR [OUT_DIR] [--verify-only]

SCIGLASS_DIR holds the export's "select" and "property" folders (files may be .csv or .csv.zip).
Two databases are written to OUT_DIR (default: SCIGLASS_DIR):

    SciGlass_mol.db   compounds in mol %
    SciGlass_wt.db    compounds in wt %

Both have elements in atomic %, the same properties and the same metadata, in the layout main.py
queries (see xlsx_to_db.py): elements / compounds / property / metadata tables joined on row_id,
plus db_info with the composition basis and property units.

Sources
    select/SciGK     one row per glass: properties, author, year, glass class (KOD, GLASNO identify it)
    select/Gcomp     full composition per glass: component, molar mass, wt %, mol %
    select/AtMol     atomic % per element (columns are atomic numbers; property/ATOMS gives symbols)
    select/Kod2Ref, select/Reference   literature references per paper (KOD)
    property/LISTPROP  SciGlass's unit for each property column (checked against reference glasses)

Units ("glass-lab" units)
    Temperatures stay in deg C. Viscosity is converted from log10(eta/P) to log10(eta/Pa.s) (minus 1),
    resistivity from log10(rho/Ohm.cm) to log10(rho/Ohm.m) (minus 2). Thermal expansion stays as
    SciGlass stores it, in units of 10^-7/K (89 means 8.9e-6/K). Mean dispersion and tan(delta),
    stored x10^4, are divided by 10^4. Everything else is unchanged (see PROPERTIES).
    SciGlass's T1..T13 (temperature at log10(eta/P) = n) become T0..T12 (log10(eta/Pa.s) = n - 1).

Data handling
    * Glass IDs are "SG-<KOD>-<GLASNO>". 46 KOD/GLASNO pairs are shared by different glasses; the
      later rows get "-2", "-3", ... Exact duplicate rows are dropped. Gcomp/AtMol hold only one
      composition per KOD/GLASNO, so a shared-ID row gets it only if its SciGK wt % columns match it.
    * Components listed twice in one glass are summed. Unnamed components are stored as "Unspecified".
    * Lumped components (e.g. "Na2O+K2O", "R2O") have no molar mass, so SciGlass has no mol % for
      those glasses; they have no composition in SciGlass_mol.db (their wt % is in SciGlass_wt.db).
    * Missing values are NULL. Zero is a real value for properties (log values can be 0), which
      db_info records as zero_is_missing = no. Absent elements/compounds are NULL.

After writing, every stored value is checked against the source tables (with the unit conversion
undone), and the number of stored values is checked against the number of source values; the script
exits non-zero on any difference.
"""

import argparse
import os
import sqlite3
import sys
from collections import Counter, defaultdict

import pandas as pd

# (SciGK column, database name, unit, scale, offset): stored = source * scale + offset
PROPERTIES = (
    [(f"T{n}", f"T{n - 1}", "°C", 1, 0) for n in range(1, 14)]
    + [(f"V{t}", f"Viscosity{t}C", "log₁₀(Pa·s)", 1, -1) for t in (500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1800, 2000, 2200)]
    + [
        ("TG", "Tg", "°C", 1, 0),
        ("LPT", "TLittleton", "°C", 1, 0),
        ("ANPT", "TAnnealing", "°C", 1, 0),
        ("SPT", "Tstrain", "°C", 1, 0),
        ("Tsoft", "Tsoft", "°C", 1, 0),
        ("Mg", "TdilatometricSoftening", "°C", 1, 0),
        ("TLiq", "Tliquidus", "°C", 1, 0),
        ("Tm", "Tmelt", "°C", 1, 0),
    ]
    + [(c, f"Resistivity{t}C", "log₁₀(Ω·m)", 1, -2) for c, t in (("RO20", 20), ("RO100", 100), ("RO150", 150), ("RO300", 300), ("ro800", 800), ("ro1000", 1000), ("ro1200", 1200), ("ro1400", 1400))]
    + [
        ("TK100C", "TK100", "°C", 1, 0),
        ("TEC55", "CTE55C", "10⁻⁷/K", 1, 0),
        ("TEC100", "CTE100C", "10⁻⁷/K", 1, 0),
        ("TEC160", "CTE160C", "10⁻⁷/K", 1, 0),
        ("TEC210", "CTE210C", "10⁻⁷/K", 1, 0),
        ("TEC350", "CTE350C", "10⁻⁷/K", 1, 0),
        ("ANY_TEC", "CTEbelowTg", "10⁻⁷/K", 1, 0),
        ("DENSITY", "Density20C", "g/cm³", 1, 0),
        ("dens800", "Density800C", "g/cm³", 1, 0),
        ("dens1000", "Density1000C", "g/cm³", 1, 0),
        ("dens1200", "Density1200C", "g/cm³", 1, 0),
        ("dens1400", "Density1400C", "g/cm³", 1, 0),
        ("spvm", "SpecificVolume", "cm³/g", 1, 0),
        ("ND300", "RefractiveIndex", "", 1, 0),
        ("nd300low", "RefractiveIndexLow", "", 1, 0),
        ("nd300hi", "RefractiveIndexHigh", "", 1, 0),
        ("DNFC300", "MeanDispersion", "", 1e-4, 0),
        ("NUD300", "AbbeNum", "", 1, 0),
        ("RTSH180", "ThermalShockRes", "K", 1, 0),
        ("MOD_UNG", "YoungModulus", "GPa", 1, 0),
        ("MOD_SDV", "ShearModulus", "GPa", 1, 0),
        ("MIKROTV", "Microhardness", "GPa", 1, 0),
        ("pois", "PoissonRatio", "", 1, 0),
        ("EPS730", "Permittivity", "", 1, 0),
        ("TGD730", "TangentOfLossAngle", "", 1e-4, 0),
        ("cond220", "ThermalConductivity", "W/(m·K)", 1, 0),
    ]
    + [(f"cp{t}", f"Cp{t}C", "J/(kg·K)", 1, 0) for t in (20, 200, 400, 800, 1000, 1200, 1400)]
    + [(c, n, "mN/m", 1, 0) for c, n in (("SUT900", "SurfaceTension900C"), ("SUT1200", "SurfaceTension1200C"), ("SUT1300", "SurfaceTension1300C"), ("SUT1400", "SurfaceTension1400C"), ("any_sut", "SurfaceTensionAboveTg"))]
    + [
        ("Tmax", "TMaxGrowthVelocity", "°C", 1, 0),
        ("Vmax", "MaxGrowthVelocity", "cm/s", 1, 0),
        ("Tn", "NucleationTemperature", "°C", 1, 0),
        ("Io", "NucleationRate", "1/(cm³·s)", 1, 0),
        ("tcr", "CrystallizationPeak", "°C", 1, 0),
        ("tx", "CrystallizationOnset", "°C", 1, 0),
    ]
)

# SciGK wt % columns used to decide which shared-ID row a Gcomp composition belongs to
FIXED_WT = {
    "WSIO2": "SiO2", "WAL2O3": "Al2O3", "WB2O3": "B2O3", "WCAO": "CaO", "WK2O": "K2O", "WNA2O": "Na2O",
    "WPBO": "PbO", "WLi2O": "Li2O", "WMgO": "MgO", "WSRO": "SrO", "WBAO": "BaO", "WZNO": "ZnO",
    "WP2O5": "P2O5", "WGEO2": "GeO2", "WZRO2": "ZrO2", "WTIO2": "TiO2", "WTEO2": "TeO2",
}

ANALYSIS = {"b": "batch", "a": "analysis"}
UNSPECIFIED = "Unspecified"
BASES = {"mol": "Compounds: mol %; elements: at %", "wt": "Compounds: wt %; elements: at %"}
CHUNK = 5000


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def find(base: str, *parts: str) -> str:
    path = os.path.join(base, *parts)
    for candidate in (path, path + ".zip"):
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(f"{path}(.zip) not found")


def read_table(base: str, folder: str, name: str, **kw) -> pd.DataFrame:
    path = find(base, folder, f"{name}.csv")
    sep = "\t" if folder == "select" else ","
    return pd.read_csv(path, sep=sep, low_memory=False, **kw)


def parse_gcomp(text) -> dict:
    """{component: (wt %, mol % or None)} from a Gcomp string (fields separated by 0x7F: name, molar mass,
    wt %, mol %). Repeated components are summed; mol % is None when it can't be computed."""
    if not isinstance(text, str):
        return {}
    fields = text.split("\x7f")
    if fields and fields[0] == "":
        fields = fields[1:]
    if fields and fields[-1] == "":
        fields = fields[:-1]
    if len(fields) % 4:
        raise ValueError(f"malformed composition: {text!r}")
    comp = {}
    for i in range(0, len(fields), 4):
        name, mw, wt, mol = fields[i:i + 4]
        name = name.strip() or UNSPECIFIED
        old = comp.get(name, (0.0, 0.0))
        comp[name] = (old[0] + float(wt), old[1] + float(mol), float(mw))
    no_mol = any(v[2] == 0 for v in comp.values()) or sum(v[1] for v in comp.values()) == 0
    return {name: (wt, None if no_mol else mol) for name, (wt, mol, _) in comp.items()}


SGK_COLUMNS = ["KOD", "GLASNO", "Author", "Year", "Glass_Class", "Trademark", "Analysis"] + list(FIXED_WT) + [p[0] for p in PROPERTIES]


def read_sciglass(base: str):
    """SciGK rows (only the columns used) as tuples in source order, exact duplicate rows dropped."""
    sg = read_table(base, "select", "SciGK")
    n_raw = len(sg)
    sg = sg.drop_duplicates()
    return list(sg[SGK_COLUMNS].itertuples(index=False, name=None)), n_raw - len(sg)


COL = {c: i for i, c in enumerate(SGK_COLUMNS)}


def read_compositions(base: str):
    gcomp = read_table(base, "select", "Gcomp", dtype={"Composition": str})
    return {(k, g): parse_gcomp(c) for k, g, c in zip(gcomp.Kod, gcomp.GlasNo, gcomp.Composition)}


def read_atoms(base: str):
    atoms = read_table(base, "property", "ATOMS")
    symbol = dict(zip(atoms.ID.astype(str), atoms.Name))
    atmol = read_table(base, "select", "AtMol")
    names = [symbol[c] for c in atmol.columns[2:]]
    at = {}
    for row in atmol.itertuples(index=False, name=None):
        at[(row[0], row[1])] = {names[i]: float(v) for i, v in enumerate(row[2:]) if v == v and v != 0}
    return names, at


def matches(row, comp) -> bool:
    """Does this SciGK row's wt % of the common oxides agree with a Gcomp composition?"""
    for col, name in FIXED_WT.items():
        value = row[COL[col]]
        value = value if value == value else 0
        if abs(value - comp.get(name, (0, None))[0]) > 0.02:
            return False
    return True


def assign_ids(rows, comps, at):
    """Glass IDs plus the composition and atoms each row gets (empty for unresolvable shared IDs)."""
    counts = defaultdict(int)
    for row in rows:
        counts[(row[0], row[1])] += 1
    seen = defaultdict(int)
    out = []
    for row in rows:
        key = (row[0], row[1])
        seen[key] += 1
        gid = f"SG-{key[0]}-{key[1]}" + (f"-{seen[key]}" if seen[key] > 1 else "")
        comp, atoms = comps.get(key, {}), at.get(key, {})
        if counts[key] > 1 and not matches(row, comp):
            comp, atoms = {}, {}
        out.append((gid, comp, atoms))
    return out


def read_references(base: str):
    k2r = read_table(base, "select", "Kod2Ref")
    ref = read_table(base, "select", "Reference")
    by_id = {r["Refer_ID"]: r for r in ref.to_dict("records")}
    refs = defaultdict(list)
    for kod, rid in sorted(zip(k2r.Kod, k2r.RefID)):
        if rid in by_id:
            refs[kod].append(by_id[rid])
    return refs


def text(v):
    return None if v is None or v != v or str(v).strip() == "" else str(v).strip()


def metadata_for(row, refs) -> dict:
    paper = refs.get(row[COL["KOD"]], [])
    first = paper[0] if paper else {}
    analysis = text(row[COL["Analysis"]])
    year = row[COL["Year"]]
    return {
        "Author": text(row[COL["Author"]]),
        "Year": int(year) if year == year else None,
        "Journal": text(first.get("JOURNAL")),
        "Title": text(first.get("Title")),
        "References": " | ".join(t for t in (text(r.get("FullDescr")) or text(r.get("Descr")) for r in paper) if t) or None,
        "GlassClass": text(row[COL["Glass_Class"]]),
        "Trademark": text(row[COL["Trademark"]]),
        "CompositionSource": ANALYSIS.get(analysis, analysis),
        "KOD": int(row[COL["KOD"]]),
        "GLASNO": int(row[COL["GLASNO"]]),
    }


METADATA_TYPES = {"Year": "INTEGER", "KOD": "INTEGER", "GLASNO": "INTEGER"}
META_COLUMNS = ["Author", "Year", "Journal", "Title", "References", "GlassClass", "Trademark", "CompositionSource", "KOD", "GLASNO"]


def convert(value, prop):
    if value is None or value != value:
        return None
    return float(value) * prop[3] + prop[4]


def write_db(path, basis, rows, assigned, el_names, refs, compounds):
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = sqlite3.connect(tmp)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    idx = 0 if basis == "wt" else 1
    prop_idx = [COL[p[0]] for p in PROPERTIES]
    tables = {
        "elements": (el_names, lambda row, comp, atoms: [atoms.get(e) for e in el_names]),
        "compounds": (compounds, lambda row, comp, atoms: [comp[c][idx] if c in comp else None for c in compounds]),
        "property": ([p[1] for p in PROPERTIES], lambda row, comp, atoms: [convert(row[i], p) for i, p in zip(prop_idx, PROPERTIES)]),
        "metadata": (META_COLUMNS, lambda row, comp, atoms: list(metadata_for(row, refs).values())),
    }
    for table, (cols, values) in tables.items():
        typ = lambda c: (METADATA_TYPES.get(c, "TEXT") if table == "metadata" else "REAL")
        defs = ", ".join(f"{quote(f'{table}_{c}')} {typ(c)}" for c in cols)
        conn.execute(f"CREATE TABLE {table} (row_id TEXT PRIMARY KEY, {defs})")
        sql = f"INSERT INTO {table} VALUES ({', '.join('?' * (len(cols) + 1))})"
        for start in range(0, len(rows), CHUNK):
            batch = zip(rows[start:start + CHUNK], assigned[start:start + CHUNK])
            conn.executemany(sql, ([gid] + values(row, comp if (idx == 0 or not comp or next(iter(comp.values()))[1] is not None) else {}, atoms)
                                   for row, (gid, comp, atoms) in batch))
        conn.commit()
    conn.execute("CREATE TABLE db_info (key TEXT PRIMARY KEY, value TEXT)")
    info = [("composition_basis", BASES[basis]), ("zero_is_missing", "no"), ("source", "SciGlass (raw table export), converted by sciglass_to_db.py")]
    info += [(f"unit:{name}", unit) for _, name, unit, _, _ in PROPERTIES]
    conn.executemany("INSERT INTO db_info VALUES (?, ?)", info)
    conn.commit()
    conn.close()
    os.replace(tmp, path)
    print(f"Wrote {path} ({os.path.getsize(path) / 1e6:.0f} MB)")


def verify(path, basis, base) -> bool:
    """Re-read the sources and compare every stored value; also check nothing extra or missing."""
    print(f"Verifying {path} ...")
    problems = []
    idx = 0 if basis == "wt" else 1
    rows, _ = read_sciglass(base)
    comps = read_compositions(base)
    _, at = read_atoms(base)
    expected = assign_ids(rows, comps, at)

    conn = sqlite3.connect(path)
    ids = [r[0] for r in conn.execute("SELECT row_id FROM metadata ORDER BY rowid")]
    if ids != [e[0] for e in expected]:
        problems.append(f"glass IDs/order differ from SciGK ({len(ids)} in database, {len(expected)} expected)")

    def check(table, expect_row):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")][1:]
        names = [c[len(table) + 1:] for c in cols]
        n_db = n_src = 0
        cursor = conn.execute(f"SELECT row_id, {', '.join(quote(c) for c in cols)} FROM {table} ORDER BY rowid")
        for (row_id, *values), row, (gid, comp, atoms) in zip(cursor, rows, expected):
            got = {n: v for n, v in zip(names, values) if v is not None}
            want = expect_row(row, comp, atoms)
            n_db += len(got)
            n_src += len(want)
            if set(got) != set(want) or any(abs(got[n] - want[n]) > 1e-9 * max(1.0, abs(want[n])) for n in got):
                bad = sorted(n for n in set(got) | set(want) if n not in got or n not in want or abs(got[n] - want[n]) > 1e-9 * max(1.0, abs(want[n])))
                problems.append(f"{table} {row_id}: {bad[:5]}")
        print(f"  {table}: {n_db} values stored, {n_src} in the sources")

    # properties: undo the unit conversion before comparing with SciGK
    def props(row, comp, atoms):
        return {p[1]: float(row[COL[p[0]]]) * p[3] + p[4] for p in PROPERTIES if row[COL[p[0]]] == row[COL[p[0]]]}

    def compounds(row, comp, atoms):
        if not comp or (idx == 1 and next(iter(comp.values()))[1] is None):
            return {}
        return {n: v[idx] for n, v in comp.items()}

    check("property", props)
    check("compounds", compounds)
    check("elements", lambda row, comp, atoms: atoms)
    conn.close()

    for p in problems[:30]:
        print("  MISMATCH:", p)
    if problems:
        print(f"FAILED: {len(problems)} problem(s)")
        return False
    print("OK: every stored value matches its source, and every source value is stored")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sciglass_dir")
    parser.add_argument("out_dir", nargs="?")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    out = args.out_dir or args.sciglass_dir
    paths = {b: os.path.join(out, f"SciGlass_{b}.db") for b in BASES}

    if not args.verify_only:
        base = args.sciglass_dir
        print("Reading SciGlass tables ...")
        rows, dropped = read_sciglass(base)
        comps = read_compositions(base)
        el_names, at = read_atoms(base)
        refs = read_references(base)
        assigned = assign_ids(rows, comps, at)
        shared = sum(1 for (gid, comp, atoms), row in zip(assigned, rows) if not comp and comps.get((row[0], row[1])))
        print(f"  {len(rows)} glasses ({dropped} exact duplicate rows dropped; {shared} shared-ID rows without composition)")
        for basis, path in paths.items():
            idx = 0 if basis == "wt" else 1
            usage = Counter(c for _, comp, _ in assigned for c, v in comp.items() if v[idx] is not None)
            compounds = [c for c, _ in usage.most_common()]  # most-used first
            if len(compounds) > 1900:
                print(f"Error: {len(compounds)} compounds exceed SQLite's column limit", file=sys.stderr)
                return 2
            write_db(path, basis, rows, assigned, el_names, refs, compounds)
    ok = all([verify(path, basis, args.sciglass_dir) for basis, path in paths.items()])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
