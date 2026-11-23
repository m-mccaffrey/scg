import sys
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QLabel, QWidget, QListWidget, QListWidgetItem, QPushButton, QGridLayout, QAbstractItemView, QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from ui_main import Ui_MainWidget
from typing import List, Callable
import re
from collections import Counter
import sqlite3
from numpy import nan
import sqlite3
from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QColor
import manifest
import os
import settings
import pandas as pd
from chemistry import group_elements, to_subscript
from search_csv import SearchSpec, SearchCsvError, write_search_csv, read_search_csv


class HighlightColumnDelegate(QStyledItemDelegate):
    def __init__(self, highlighted_columns, parent=None):
        super().__init__(parent)
        self.highlighted_columns = highlighted_columns

    def paint(self, painter, option, index):
        if index.column() in self.highlighted_columns:
            painter.fillRect(option.rect, QColor(0xA4, 0x94, 0))  # Highlight color
        super().paint(painter, option, index)

    def updateHighlightedColumns(self, columns):
        self.highlighted_columns = columns
        self.parent().viewport().update()


def filter_compounds_by_elements(compounds: List[str], elements: List[str]) -> List[str]:
    # Precompile a regular expression pattern for splitting compounds
    compound_pattern = re.compile(r"([A-Z][a-z]?)")

    # Filter compounds that contain any of the elements
    filtered_compounds = [compound for compound in compounds if any(element in re.findall(compound_pattern, compound) for element in elements)]

    return filtered_compounds


class ListWidget(QListWidget):
    def __init__(self, items: List[str], handler: Callable) -> None:
        super().__init__()

        self.widget = QWidget()  # Create a new QWidget
        self.grid = QGridLayout(self.widget)  # Set the grid layout to the new QWidget

        self.setSelectionMode(QAbstractItemView.MultiSelection)
        self.addItems(items)
        self.itemSelectionChanged.connect(handler)
        self.grid.addWidget(self, 1, 1, 1, 2)

        # Add 'Select All' and 'Select None' buttons
        select_all_button = QPushButton("All")
        select_all_button.clicked.connect(self.selectAll)
        self.grid.addWidget(select_all_button, 2, 1, 1, 1)

        select_none_button = QPushButton("None")
        select_none_button.clicked.connect(self.clearSelection)
        self.grid.addWidget(select_none_button, 2, 2, 1, 1)

        # parent.addItem(self.grid)


# Tables every searchable database must contain (joined on row_id in build_sql_query)
REQUIRED_TABLES = ("compounds", "elements", "property", "metadata")


def open_database(path: str) -> sqlite3.Connection:
    """Open a SciGlass-format database, raising ValueError if it is missing or not in the expected format."""
    if not os.path.isfile(path):
        raise ValueError(f"Database file not found:\n{path}")
    conn = sqlite3.connect(path)
    try:
        tables = {row[0].lower() for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        conn.close()
        raise ValueError(f"Not a valid SQLite database:\n{path}\n\n{e}")
    missing = [t for t in REQUIRED_TABLES if t not in tables]
    if missing:
        conn.close()
        raise ValueError(f"{os.path.basename(path)} is missing required table(s): {', '.join(missing)}")
    return conn


# Most glasses a search loads (the total is still counted); large databases would otherwise run out of memory
MAX_RESULTS = 50_000

# The four tables, joined on row_id
JOIN_CLAUSE = """
    compounds
    JOIN elements ON compounds.row_id = elements.row_id
    JOIN property ON compounds.row_id = property.row_id
    JOIN metadata ON compounds.row_id = metadata.row_id
"""

# Constraint-builder table names for each database table
TABLE_LABELS = {"elements": "Elements", "compounds": "Compounds", "property": "Property", "metadata": "Metadata"}


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def read_database_columns(conn: sqlite3.Connection) -> dict:
    """{table: [column names without the '<table>_' prefix]} for an open database, in table order."""
    columns = {}
    for table in REQUIRED_TABLES:
        prefix = f"{table}_"
        columns[table] = [
            row[1][len(prefix):] for row in conn.execute(f"PRAGMA table_info({quote_identifier(table)})") if row[1].startswith(prefix)
        ]
    return columns


def read_database_info(conn: sqlite3.Connection) -> dict:
    """Optional key/value notes stored by xlsx_to_db.py (composition basis, "unit:<property>" entries)."""
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM db_info")}
    except sqlite3.Error:
        return {}


def display_column_names(columns: List[str], label: Callable[[str, str], str] = lambda table, name: name) -> List[str]:
    """Result-column headings from "<table>_<name>" database columns ("id" for row_id).
    label(table, name) formats each heading; a name found in more than one table gets its table added,
    e.g. "Si [Compounds]"."""
    parts = [("metadata", "id") if col == "row_id" else tuple(col.split("_", 1)) for col in columns]
    counts = Counter(name for _, name in parts)
    headings = []
    for (table, name), col in zip(parts, columns):
        text = "id" if col == "row_id" else label(table, name)
        if col != "row_id" and counts[name] > 1:
            text += f" [{TABLE_LABELS.get(table, table)}]"
        headings.append(text)
    return headings


def order_result_columns(columns: List[str], constrained: List[str]) -> List[str]:
    """Move the constrained columns (in constraint order) together, just left of the property columns.
    row_id stays first."""
    stacked = [c for c in constrained if c in columns and c != "row_id"]
    rest = [c for c in columns if c not in stacked]
    insert_at = next(
        (i for i, c in enumerate(rest) if c.startswith("property_")),
        next((i for i, c in enumerate(rest) if c.startswith("metadata_")), len(rest)),
    )
    return rest[:insert_at] + stacked + rest[insert_at:]


# Item data role holding a list item's real (database) name; the visible text may be formatted
NAME_ROLE = Qt.UserRole


def item_name(item: QListWidgetItem) -> str:
    return item.data(NAME_ROLE)


def selected_names(widget: QListWidget) -> List[str]:
    return [item_name(item) for item in widget.selectedItems() if item_name(item) is not None]


class ConstraintColumnDelegate(QStyledItemDelegate):
    """Shows the constraint's column with subscripts/units; the stored text stays the database name."""

    def __init__(self, label: Callable[[str, str], str], parent=None):
        super().__init__(parent)
        self.label = label

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        table = str(index.siblingAtColumn(0).data() or "").lower()
        if option.text and option.text != "id":
            option.text = self.label(table, option.text)


# Column in the constraints model holding the "Allow Missing" checkbox
ALLOW_MISSING_COL = 6


def allows_missing_option(table: str) -> bool:
    """Only properties can have unknown values; a 0 in a composition column means "not present"."""
    return str(table).strip().lower() == "property"


def make_constraint_items(values: List[str]) -> List[QStandardItem]:
    """Build a constraints-model row. values[ALLOW_MISSING_COL] is truthy ("Yes") to check Allow Missing,
    which is only offered on Property constraints."""
    values = (list(values) + [""] * (ALLOW_MISSING_COL + 1))[: ALLOW_MISSING_COL + 1]
    items = []
    for i, value in enumerate(values):
        if i == ALLOW_MISSING_COL:
            item = QStandardItem()
            item.setEditable(False)
            if allows_missing_option(values[0]):
                item.setCheckable(True)
                checked = str(value).strip().lower() in ("yes", "true", "1", "y", "x")
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            else:
                item.setEnabled(False)
        elif isinstance(value, float):
            item = QStandardItem(f"{value:.10g}")
        else:
            item = QStandardItem(str(value))
        items.append(item)
    return items


def constraint_row_values(model: QStandardItemModel, row: int) -> List[str]:
    """Read a constraints-model row as strings; Allow Missing becomes "Yes" or ""."""
    values = []
    for col in range(model.columnCount()):
        item = model.item(row, col)
        if col == ALLOW_MISSING_COL:
            checked = item is not None and item.isCheckable() and item.checkState() == Qt.Checked
            values.append("Yes" if checked and allows_missing_option(values[0]) else "")
        else:
            values.append(item.text() if item is not None else "")
    return values


class MainWindow(QWidget, Ui_MainWidget):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(manifest.ICON_FILE_NAME))

        # Connect to SQLite database
        self.conn = None
        self.db_path = None
        self.dbLabel = QLabel(self)
        self.chooseDbButton = QPushButton("Choose Database...", self)
        self.chooseDbButton.clicked.connect(self.choose_database)
        self.bottom_layout.addWidget(self.dbLabel, 2, 0, 1, 1, Qt.AlignRight | Qt.AlignVCenter)
        self.bottom_layout.addWidget(self.chooseDbButton, 2, 1, 1, 1)
        # Set the window icon
        self.setWindowTitle(f"{manifest.APP_TITLE} Version {manifest.APP_VERSION} (Build {manifest.APP_BUILD})")

        # Column lists, units and composition basis come from the open database (see load_database_columns)
        self.elements: List[str] = []
        self.compounds: List[str] = []
        self.properties: List[str] = []
        self.metadata_columns: List[str] = []
        self.units: dict = {}
        self.composition_basis = ""
        # whether a 0 in a property/metadata column means "no data" (compositions: 0 always means absent)
        self.zero_is_missing = True

        # note under the results saying what the composition numbers mean
        self.compositionLabel = QLabel(self)
        self.compositionLabel.setWordWrap(True)
        self.layout.addWidget(self.compositionLabel)

        def setup_list_widget(
            widget: QListWidget, get_items: Callable[[], List[str]], handler: Callable, btn_all: QPushButton, btn_none: QPushButton, line_search: QLineEdit
        ):
            widget.itemSelectionChanged.connect(handler)
            btn_all.clicked.connect(widget.selectAll)
            btn_none.clicked.connect(widget.clearSelection)

            def filter_list():
                # show matching items plus anything already selected, keeping the selection
                selected = selected_names(widget)
                query = line_search.text().lower()
                names = [name for name in get_items() if query in name.lower() or name in selected]
                self.fill_list(widget, names, selected)

            line_search.textChanged.connect(filter_list)

        setup_list_widget(
            self.elementsListWidget, lambda: self.elements, self.element_list_handler, self.btnAllElements, self.btnNoneElements, self.lineElementSearch
        )
        setup_list_widget(
            self.compoundsListWidget, lambda: self.compounds, self.compound_list_handler, self.btnAllCompounds, self.btnNoneCompounds, self.lineCompoundSearch
        )
        setup_list_widget(
            self.propertiesListWidget,
            lambda: self.properties,
            self.property_list_handler,
            self.btnAllProperties,
            self.btnNoneProperties,
            self.linePropertySearch,
        )

        # Constraint List Widget
        self.constraintsModel = QStandardItemModel()
        self.constraintsListWidget.setModel(self.constraintsModel)
        self.constraintsModel.setHorizontalHeaderLabels(["", "", "", "", "OR Group", "Tolerance", "Allow Missing"])
        self.constraintsModel.horizontalHeaderItem(ALLOW_MISSING_COL).setToolTip(
            "Property constraints only: when checked, materials with no data for this property are not excluded by this constraint."
        )
        self.constraintColumnDelegate = ConstraintColumnDelegate(self.column_label, self.constraintsListWidget)
        self.constraintsListWidget.setItemDelegateForColumn(1, self.constraintColumnDelegate)

        # Dropdown for table columns
        self.tableDropdown.currentTextChanged.connect(self.update_columns)

        # Connect buttons to respective functions
        self.addButton.clicked.connect(self.addConstraint)
        self.removeButton.clicked.connect(self.removeConstraint)

        # Table View
        self.model = QStandardItemModel(self)
        self.tableView.setModel(self.model)

        self.highlightDelegate = HighlightColumnDelegate([], self.tableView)
        self.tableView.setItemDelegate(self.highlightDelegate)

        # Load Button
        self.load_button.clicked.connect(self.fetchData)

        # Pagination attributes
        self.currentPage = 0
        self.rowsPerPage = 10  # Adjust the number of rows per page as needed

        self.prevPageButton.clicked.connect(self.prevPage)

        self.nextPageButton.clicked.connect(self.nextPage)

        # add_constraints_from_row button
        self.add_constraints_from_row_button.clicked.connect(self.add_constraints_from_row)

        # export to csv button
        self.export_button.clicked.connect(self.export_to_csv)

        # import search from csv button
        self.btnImport.clicked.connect(self.import_from_csv)

        # open the saved database (or SciGlass.db by default)
        self.set_database(settings.get_database_path(), save=False)

    @property
    def new_constraint(self):
        return [
            self.tableDropdown.currentText(),
            self.columnDropdown.currentData() or "",
            self.comparisonDropdown.currentText(),
            self.valueField.text(),
            "",
            "",
            "",
        ]

    # setter for new_constraint
    @new_constraint.setter
    def new_constraint(self, new_constraint):
        self.tableDropdown.setCurrentText(new_constraint[0])
        self.columnDropdown.setCurrentIndex(self.columnDropdown.findData(new_constraint[1]))
        self.comparisonDropdown.setCurrentText(new_constraint[2])
        self.valueField.setText(str(new_constraint[3]))

    def current_search_spec(self) -> SearchSpec:
        constraints = [constraint_row_values(self.constraintsModel, row) for row in range(self.constraintsModel.rowCount())]
        return SearchSpec(
            constraints=constraints,
            elements=selected_names(self.elementsListWidget),
            compounds=selected_names(self.compoundsListWidget),
            properties=selected_names(self.propertiesListWidget),
        )

    def export_to_csv(self):
        df = getattr(self, "df", None)
        if df is None:
            QMessageBox.information(self, "Export to CSV", "Fetch data before exporting.")
            return

        # create a temporary copy of the dataframe to avoid modifying the original
        df_copy = df.copy()
        # remove table names from column headers; add units (plain text formulas, for spreadsheets)
        df_copy.columns = display_column_names(
            list(df_copy.columns), lambda table, name: self.column_label(table, name, subscripts=False)
        )

        filename, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"

        # save the constraints used for this search (as of the last fetch) ahead of the results
        spec = getattr(self, "last_search_spec", None) or self.current_search_spec()
        try:
            database = {"File": os.path.basename(self.db_path or ""), "Compositions": self.composition_basis or "not recorded"}
            total = getattr(self, "total_matches", len(df_copy))
            if total > len(df_copy):
                database["Rows"] = f"first {len(df_copy)} of {total} matches"
            write_search_csv(filename, spec, df_copy, database)
        except OSError as e:
            QMessageBox.critical(self, "Export to CSV", f"Could not write {filename}:\n{e}")
            return
        if total > len(df_copy):
            QMessageBox.information(
                self, "Export to CSV", f"Exported the first {len(df_copy):,} of {total:,} matching glasses. Narrow the search to export the rest."
            )

    def import_from_csv(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Search From CSV", "", "CSV Files (*.csv);;All Files (*)")
        if not filename:
            return
        try:
            spec = read_search_csv(filename)
        except (SearchCsvError, OSError, UnicodeDecodeError) as e:
            QMessageBox.warning(self, "Import From CSV", str(e))
            return

        self.apply_search_spec(spec)

        if spec.constraints:
            self.currentPage = 0
            try:
                self.fetchData()
            except Exception as e:
                QMessageBox.warning(self, "Import From CSV", f"Search restored, but fetching data failed:\n{e}")

    def apply_search_spec(self, spec: SearchSpec):
        # clear the search boxes so every list item is available to be selected
        for line in (self.lineElementSearch, self.lineCompoundSearch, self.linePropertySearch):
            line.clear()

        def select_items(widget: QListWidget, wanted: List[str], handler: Callable):
            wanted = set(wanted)
            widget.blockSignals(True)
            widget.clearSelection()
            for i in range(widget.count()):
                item = widget.item(i)
                if item_name(item) in wanted:
                    item.setSelected(True)
            widget.blockSignals(False)
            handler()

        # elements first: selecting elements repopulates the compounds list
        select_items(self.elementsListWidget, spec.elements, self.element_list_handler)
        select_items(self.compoundsListWidget, spec.compounds, self.compound_list_handler)
        select_items(self.propertiesListWidget, spec.properties, self.property_list_handler)

        self.constraintsModel.removeRows(0, self.constraintsModel.rowCount())
        for constraint in spec.constraints:
            self.constraintsModel.appendRow(make_constraint_items(constraint))
        self.constraintsListWidget.resizeColumnsToContents()

    def build_sql_query(self):
        where_clause = self.build_where_clause()
        return f"SELECT * FROM {JOIN_CLAUSE}" + (f" WHERE {where_clause}" if where_clause else "")

    def build_where_clause(self) -> str:
        or_groups = {}
        ungrouped_clauses = []

        # Iterate over the rows in the constraintsModel
        for row in range(self.constraintsModel.rowCount()):
            table = self.constraintsModel.item(row, 0).text().lower()
            feature = self.constraintsModel.item(row, 1).text()
            if feature == "id":
                column = "row_id"
            else:
                column = f"{table}_{feature}"
            field = f"{quote_identifier(table)}.{quote_identifier(column)}"
            operator = self.constraintsModel.item(row, 2).text()
            value = self.constraintsModel.item(row, 3).text()
            or_group = self.constraintsModel.item(row, 4).text()  # Assuming OR group number is in the fifth column
            tolerance = self.constraintsModel.item(row, 5).text()  # Assuming tolerance is in the sixth column
            allow_missing_item = self.constraintsModel.item(row, ALLOW_MISSING_COL)
            allow_missing = (
                allows_missing_option(table)
                and allow_missing_item is not None
                and allow_missing_item.isCheckable()
                and allow_missing_item.checkState() == Qt.Checked
            )

            # if operator is "=" and tolerance is not empty, change operator to BETWEEN, and add two conditions
            if operator == "=" and tolerance != "":
                operator = "BETWEEN"
                value = f"{float(value) - float(tolerance)} AND {float(value) + float(tolerance)}"
                condition = f"{field} {operator} {value}"
            else:
                escaped = value.replace("'", "''")
                condition = f"{field} {operator} '{escaped}'"

            # Missing data is NULL (or 0, in databases that store missing values as 0);
            # optionally let those rows through this constraint
            if allow_missing:
                if self.zero_is_missing:
                    condition = f"({condition} OR {field} IS NULL OR {field} = 0 OR {field} = '')"
                else:
                    condition = f"({condition} OR {field} IS NULL)"

            # Group the conditions or add to ungrouped
            if or_group != "":
                or_groups.setdefault(or_group, []).append(condition)
            else:
                ungrouped_clauses.append(condition)

        # Build WHERE clause with OR conditions within groups and AND between groups
        grouped_where_clause = " AND ".join([f"({' OR '.join(conditions)})" for conditions in or_groups.values()])
        ungrouped_where_clause = " AND ".join(ungrouped_clauses)
        return " AND ".join(filter(None, [grouped_where_clause, ungrouped_where_clause]))

    def run_search(self):
        """Run the constraints and return (column names, rows) for the matching glasses, fetching only
        columns that have data for at least one match (plus the constrained columns). Large databases
        have hundreds of mostly empty columns, so this keeps broad searches fast."""
        where_clause = self.build_where_clause()
        cur = self.conn.cursor()
        cur.execute("DROP TABLE IF EXISTS temp.matches")
        cur.execute("CREATE TEMP TABLE matches (row_id, n INTEGER PRIMARY KEY)")
        cur.execute(
            f"INSERT INTO temp.matches (row_id) SELECT compounds.row_id FROM {JOIN_CLAUSE}"
            + (f" WHERE {where_clause}" if where_clause else "")
            + " ORDER BY compounds.rowid"
        )
        self.total_matches = cur.execute("SELECT count(*) FROM temp.matches").fetchone()[0]
        cur.execute("DELETE FROM temp.matches WHERE n > ?", (MAX_RESULTS,))
        cur.execute("CREATE INDEX temp.matches_row_id ON matches (row_id)")

        constrained = set(self.constrained_db_columns())
        selected = []
        for table in REQUIRED_TABLES:
            columns = [r[1] for r in cur.execute(f"PRAGMA table_info({quote_identifier(table)})") if r[1] != "row_id"]
            if not columns:
                continue
            zero_empty = table in ("elements", "compounds") or self.zero_is_missing
            counts = cur.execute(
                "SELECT "
                + ", ".join(f"count(NULLIF({quote_identifier(c)}, 0))" if zero_empty else f"count({quote_identifier(c)})" for c in columns)
                + f" FROM {quote_identifier(table)} JOIN temp.matches m ON {quote_identifier(table)}.row_id = m.row_id"
            ).fetchone()
            selected += [f"{quote_identifier(table)}.{quote_identifier(c)}" for c, n in zip(columns, counts) if n or c in constrained]

        cur.execute(
            "SELECT m.row_id" + "".join(f", {c}" for c in selected)
            + " FROM temp.matches m"
            + "".join(f" JOIN {quote_identifier(t)} ON {quote_identifier(t)}.row_id = m.row_id" for t in REQUIRED_TABLES)
            + " ORDER BY m.n"
        )
        rows = cur.fetchall()
        return [d[0] for d in cur.description], rows

    # For the selected cells in the tableView, create a new constraint for each of the nonzero (and not nan) values and add it to the constraintsModel
    # This is achieved by adding a constraint regardless of the values in the dropdowns and field, and then editing the constraint to match the values in the row
    def add_constraints_from_row(self):
        # Create empty list of new constraints
        new_constraints = []
        # Get the selected cells
        selected_indexes = self.tableView.selectedIndexes()
        # for each selected cell, append the associated column name, the table that column is in, and the value in the cell to the new_constraints list
        for index in selected_indexes:
            # the table and column come from the result column's "<table>_<name>" database name
            db_column = self.df.columns[index.column()]
            if db_column == "row_id":
                table, column_name = "Metadata", "id"
            else:
                table_key, column_name = db_column.split("_", 1)
                table = TABLE_LABELS[table_key]
            value = self.model.item(index.row(), index.column()).text()
            if value == "":
                continue  # no data in this cell
            # set variable for tolerance to be 1% of the value (numbers only)
            try:
                tolerance = str(abs(float(value)) * 0.01)
            except ValueError:
                tolerance = ""
            new_constraints.append([table, column_name, "=", value, "", tolerance])

        # for each new constraint, add it to the constraintsModel
        for constraint in new_constraints:
            self.constraintsModel.appendRow(make_constraint_items(constraint))
        self.constraintsListWidget.resizeColumnsToContents()

    def column_label(self, table: str, name: str, subscripts: bool = True, units: bool = True) -> str:
        """How a column is shown to the user: compound formulas with subscripts, properties with their unit."""
        table = table.lower()
        text = to_subscript(name) if subscripts and table == "compounds" else name
        unit = self.units.get(name) if units and table == "property" else None
        return f"{text} ({unit})" if unit else text

    def fill_list(self, widget: QListWidget, names: List[str], selected=()):
        """Rebuild a selection list. Elements are grouped under headings, compounds shown with subscripts,
        properties with their unit as a tooltip. Each item keeps its database name in NAME_ROLE."""
        selected = set(selected)
        grouped = widget is self.elementsListWidget
        if grouped:
            sections = group_elements(list(names))
        else:
            sections = {None: list(names)}
        table = "compounds" if widget is self.compoundsListWidget else ""

        widget.blockSignals(True)
        widget.clear()
        for heading, members in sections.items():
            if heading is not None:
                header = QListWidgetItem(heading)
                header.setFlags(Qt.ItemIsEnabled)  # visible, not selectable
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                widget.addItem(header)
            for name in members:
                text = self.column_label(table, name, units=False)
                item = QListWidgetItem(f"    {text}" if grouped else text)
                item.setData(NAME_ROLE, name)
                if widget is self.propertiesListWidget and self.units.get(name):
                    item.setToolTip(f"Unit: {self.units[name]}")
                widget.addItem(item)
                if name in selected:
                    item.setSelected(True)
        widget.blockSignals(False)

    def update_columns(self):
        self.selected_elements = selected_names(self.elementsListWidget)
        self.selected_compounds = selected_names(self.compoundsListWidget)
        self.selected_properties = selected_names(self.propertiesListWidget)
        self.selected_metadata = self.metadata_columns + ["id"]

        selection = self.tableDropdown.currentText()
        names = {
            "Elements": self.selected_elements,
            "Compounds": self.selected_compounds,
            "Property": self.selected_properties,
            "Metadata": self.selected_metadata,
        }[selection]
        self.columnDropdown.clear()
        for name in names:
            self.columnDropdown.addItem(self.column_label(selection, name), name)

    def element_list_handler(self):
        self.selected_elements = selected_names(self.elementsListWidget)
        self.filtered_compounds = filter_compounds_by_elements(self.compounds, self.selected_elements)
        self.fill_list(self.compoundsListWidget, self.filtered_compounds)
        self.update_columns()

    def compound_list_handler(self):
        self.selected_compounds = selected_names(self.compoundsListWidget)
        self.update_columns()

    def property_list_handler(self):
        self.selected_properties = selected_names(self.propertiesListWidget)
        self.update_columns()

    def fetchData(self):
        self.selected_compounds = selected_names(self.compoundsListWidget)
        self.unselected_compounds = [c for c in self.compounds if c not in self.selected_compounds]

        self.selected_properties = selected_names(self.propertiesListWidget)
        self.unselected_properties = [p for p in self.properties if p not in self.selected_properties]

        if self.conn is None:
            QMessageBox.warning(self, "Fetch Data", "No database is open. Use Choose Database... to select one.")
            return

        # Build and execute the SQL query
        try:
            column_names, query_results = self.run_search()
        except (sqlite3.Error, ValueError) as e:
            QMessageBox.warning(
                self, "Fetch Data", f"The search could not be run. Check that every constraint refers to a column in this database.\n\n{e}"
            )
            return

        # remember the search that produced these results, for export
        self.last_search_spec = self.current_search_spec()

        # Get the total number of results
        if self.total_matches > len(query_results):
            self.totalResultsLabel.setText(
                f"Total Results: {self.total_matches:,} (showing the first {len(query_results):,}; narrow the search to see the rest)"
            )
        else:
            self.totalResultsLabel.setText(f"Total Results: {len(query_results)}")

        # Create the DataFrame
        self.df = pd.DataFrame(query_results, columns=column_names)

        # every table has a row_id; keep just one
        self.df = self.df.loc[:, ~self.df.columns.duplicated()]

        # A 0 composition means the component is absent: show it blank. In older databases a 0 property
        # also means "no data"; where the database says 0 is a real value, it is kept.
        zero_cols = [
            col for col in self.df.columns
            if col.startswith(("elements_", "compounds_")) or (self.zero_is_missing and col != "row_id")
        ]
        self.df[zero_cols] = self.df[zero_cols].replace(0, nan)

        # Drop columns where all values are NA, except constrained ones (shown even when empty)
        constrained = self.constrained_db_columns()
        empty = [col for col in self.df.columns if col not in constrained and self.df[col].isna().all()]
        self.df.drop(columns=empty, inplace=True)

        # constrained columns sit together, just left of the property columns
        self.df = self.df[order_result_columns(list(self.df.columns), constrained)]

        self.df = self.df.fillna("")

        # Extract compound columns
        # compound_columns = self.df.columns.get_level_values(0)

        # # Create the Composition string
        # composition = self.df.apply(lambda row: ', '.join(
        #     f"{to_subscript(compound)}: {100*row[compound]:.2f}%" for compound in compound_columns if row[compound] != 0 and "compound" in compound
        # ), axis=1)

        # # Add the Composition column to the DataFrame
        # self.df['Composition'] = composition

        self.currentPage = 0
        self.column_names = display_column_names(list(self.df.columns), self.column_label)

        self.setColumnTitles(self.column_names)
        self.loadData()

        constrained_columns = self.getConstrainedColumns()
        self.highlightDelegate.updateHighlightedColumns(constrained_columns)
        self.tableView.viewport().update()  # Refresh the view

    def constrained_db_columns(self) -> List[str]:
        """Database columns used by the constraints, in constraint order, without repeats."""
        columns = []
        for row in range(self.constraintsModel.rowCount()):
            table = self.constraintsModel.item(row, 0).text().lower()
            feature = self.constraintsModel.item(row, 1).text()
            column = "row_id" if feature == "id" else f"{table}_{feature}"
            if column not in columns:
                columns.append(column)
        return columns

    def getConstrainedColumns(self):
        constrained = set(self.constrained_db_columns())
        return {i for i, col in enumerate(self.df.columns) if col in constrained}

    # Function placeholders for button actions
    def addConstraint(self):
        # Logic to add constraint
        self.constraintsModel.appendRow(make_constraint_items(self.new_constraint))
        self.constraintsListWidget.resizeColumnsToContents()

    def removeConstraint(self):
        selection_model = self.constraintsListWidget.selectionModel()
        selected_indexes = selection_model.selectedIndexes()
        rows_to_remove = set(index.row() for index in selected_indexes)

        # Remove rows from the last to first to avoid index shifting issues
        for row in sorted(rows_to_remove, reverse=True):
            self.constraintsModel.removeRow(row)

    def loadData(self):
        # Adjust to load data for the current page
        startRow = self.currentPage * self.rowsPerPage
        endRow = startRow + self.rowsPerPage
        pageData = self.df.iloc[startRow:endRow]

        # Now use pageData instead of df to populate the table
        self.model.clear()
        self.setColumnTitles(self.column_names)
        for _, row in pageData.iterrows():
            self.addRow(row)

        self.updatePageLabel()
        self.tableView.resizeColumnsToContents()

    def nextPage(self):
        self.currentPage += 1
        self.loadData()

    def prevPage(self):
        if self.currentPage > 0:
            self.currentPage -= 1
            self.loadData()

    def updatePageLabel(self):
        self.pageLabel.setText(f"Page: {self.currentPage + 1}")

    def setColumnTitles(self, titles):
        self.model.setHorizontalHeaderLabels(titles)

    def addRow(self, items):
        row = []
        for item in items:
            if isinstance(item, (float)):
                # Custom format: change '10g' to your preferred format
                formatted_item = f"{item:.5g}"
                row.append(QStandardItem(formatted_item))
            else:
                row.append(QStandardItem(str(item)))
        self.model.appendRow(row)

    def set_database(self, path: str, save: bool = True) -> bool:
        """Switch the searched database. Returns False (keeping the current one) if it can't be opened."""
        try:
            new_conn = open_database(path)
        except ValueError as e:
            if self.conn is None:
                self.dbLabel.setText("Database: (none)")
                self.dbLabel.setToolTip("")
            QMessageBox.warning(self, "Choose Database", str(e))
            return False

        if self.conn is not None:
            self.conn.close()
        self.conn = new_conn
        self.db_path = os.path.abspath(path)
        self.dbLabel.setText(f"Database: {os.path.basename(self.db_path)}")
        self.dbLabel.setToolTip(self.db_path)
        self.load_database_columns()

        # results from the previous database no longer apply
        self.df = None
        self.last_search_spec = None
        self.currentPage = 0
        self.model.clear()
        self.totalResultsLabel.setText("")

        if save:
            try:
                settings.set_database_path(self.db_path)
            except OSError as e:
                QMessageBox.warning(self, "Choose Database", f"Database opened, but the selection could not be saved:\n{e}")
        return True

    def load_database_columns(self):
        """Fill the element/compound/property lists and metadata columns from the open database."""
        columns = read_database_columns(self.conn)
        self.elements = columns["elements"]
        self.compounds = columns["compounds"]
        self.properties = columns["property"]
        self.metadata_columns = columns["metadata"]

        info = read_database_info(self.conn)
        self.units = {key[len("unit:"):]: value for key, value in info.items() if key.startswith("unit:") and value}
        self.composition_basis = info.get("composition_basis", "")
        self.zero_is_missing = info.get("zero_is_missing", "yes").strip().lower() != "no"
        notes = [f"Compositions: {self.composition_basis}" if self.composition_basis else "Composition basis: not recorded in this database"]
        if not self.units:
            notes.append("Property units: not recorded in this database")
        self.compositionLabel.setText(" · ".join(notes))

        for widget, line, items in (
            (self.elementsListWidget, self.lineElementSearch, self.elements),
            (self.compoundsListWidget, self.lineCompoundSearch, self.compounds),
            (self.propertiesListWidget, self.linePropertySearch, self.properties),
        ):
            line.blockSignals(True)
            line.clear()
            line.blockSignals(False)
            self.fill_list(widget, items)
        self.update_columns()

    def choose_database(self):
        start_dir = os.path.dirname(self.db_path) if self.db_path else settings.APP_DIR
        filename, _ = QFileDialog.getOpenFileName(
            self, "Choose Database", start_dir, "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if filename:
            self.set_database(filename)

    def __del__(self):
        # Close the database connection when the window is closed
        if self.conn is not None:
            self.conn.close()


class SciGlassExplorer(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        # Create and show the main window
        self.mainWindow = MainWindow()
        self.mainWindow.showMaximized()


# Example Usage
if __name__ == "__main__":
    app = SciGlassExplorer(sys.argv)

    sys.exit(app.exec())
