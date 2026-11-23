"""Read and write "search CSV" files.

An exported search CSV holds everything needed to recall the search that
produced it, followed by the results themselves:

    [SciGlass Explorer Search],format=1
    [Constraints]
    Table,Column,Operator,Value,OR Group,Tolerance,Allow Missing
    Elements,Si,>,0.1,,,
    Property,Tg,>=,1000,,,Yes
    [Selected Elements]
    Si,O
    [Selected Compounds]
    SiO2
    [Selected Properties]
    T0
    [Database]
    File,SciGlass_Plus.db
    Compositions,mol %
    [Results]
    <result header row>
    <result rows...>

Every line is valid CSV, so the file still opens cleanly in Excel. The [Database] section is
informational and is ignored on import. Files are written as UTF-8 with a byte-order mark so Excel
shows units and accented names correctly.
"""

import csv
import io
from dataclasses import dataclass, field
from typing import List

import pandas as pd

FORMAT_VERSION = 1
MAGIC = "[SciGlass Explorer Search]"
CONSTRAINT_HEADER = ["Table", "Column", "Operator", "Value", "OR Group", "Tolerance", "Allow Missing"]

SECTION_CONSTRAINTS = "[Constraints]"
SECTION_ELEMENTS = "[Selected Elements]"
SECTION_COMPOUNDS = "[Selected Compounds]"
SECTION_PROPERTIES = "[Selected Properties]"
SECTION_DATABASE = "[Database]"
SECTION_RESULTS = "[Results]"


@dataclass
class SearchSpec:
    constraints: List[List[str]] = field(default_factory=list)
    elements: List[str] = field(default_factory=list)
    compounds: List[str] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)


class SearchCsvError(ValueError):
    pass


def write_search_csv(path: str, spec: SearchSpec, results: pd.DataFrame = None, database: dict = None) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([MAGIC, f"format={FORMAT_VERSION}"])

        writer.writerow([SECTION_CONSTRAINTS])
        writer.writerow(CONSTRAINT_HEADER)
        for constraint in spec.constraints:
            row = [str(v) for v in constraint][: len(CONSTRAINT_HEADER)]
            row += [""] * (len(CONSTRAINT_HEADER) - len(row))
            writer.writerow(row)

        for section, items in (
            (SECTION_ELEMENTS, spec.elements),
            (SECTION_COMPOUNDS, spec.compounds),
            (SECTION_PROPERTIES, spec.properties),
        ):
            writer.writerow([section])
            writer.writerow(items)

        if database:
            writer.writerow([SECTION_DATABASE])
            for key, value in database.items():
                writer.writerow([key, value])

        writer.writerow([SECTION_RESULTS])
        if results is not None:
            f.flush()
            results.to_csv(f, index=False, lineterminator="\r\n")


def read_search_csv(path: str) -> SearchSpec:
    """Parse the search definition from a search CSV. The results section is ignored."""
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        text = f.read()

    rows = csv.reader(io.StringIO(text))
    first = next(rows, None)
    if not first or first[0].strip() != MAGIC:
        raise SearchCsvError(
            "This file does not contain a saved search. Only CSVs exported by this version of the application can be imported."
        )

    spec = SearchSpec()
    section = None
    for row in rows:
        head = row[0].strip() if row else ""
        if head == SECTION_RESULTS:
            break
        if head.startswith("[") and head.endswith("]"):
            section = head
            continue

        cells = [c.strip() for c in row]
        if section == SECTION_CONSTRAINTS:
            if not any(cells) or cells[:2] == CONSTRAINT_HEADER[:2]:
                continue
            cells = (cells + [""] * len(CONSTRAINT_HEADER))[: len(CONSTRAINT_HEADER)]
            spec.constraints.append(cells)
        elif section == SECTION_ELEMENTS:
            spec.elements.extend(c for c in cells if c)
        elif section == SECTION_COMPOUNDS:
            spec.compounds.extend(c for c in cells if c)
        elif section == SECTION_PROPERTIES:
            spec.properties.extend(c for c in cells if c)

    return spec
