import sys
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget, QListWidget, QPushButton, QGridLayout, QAbstractItemView, QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from ui_main import Ui_MainWidget
from typing import List, Callable
import re
import lists
import sqlite3
from numpy import nan
import sqlite3
from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QColor
import manifest
import pandas as pd
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


def to_subscript(compound):
    subscript_map = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    return compound.translate(subscript_map)


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


class MainWindow(QWidget, Ui_MainWidget):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(manifest.ICON_FILE_NAME))

        # Connect to SQLite database
        self.conn = sqlite3.connect("SciGlass.db")
        # Set the window icon
        self.setWindowTitle(f"{manifest.APP_TITLE} Version {manifest.APP_VERSION} (Build {manifest.APP_BUILD})")

        self.elements = lists.elements
        self.compounds = lists.compounds
        self.properties = lists.properties

        def setup_list_widget(
            widget: QListWidget, item_list: List[str], handler: Callable, btn_all: QPushButton, btn_none: QPushButton, line_search: QLineEdit
        ):
            widget.addItems(item_list)
            widget.itemSelectionChanged.connect(handler)
            btn_all.clicked.connect(widget.selectAll)
            btn_none.clicked.connect(widget.clearSelection)

            def filter_list():
                selected = list([item.text() for item in widget.selectedItems()])
                query = line_search.text()
                filtered = list([item for item in item_list if query.lower() in item.lower()])
                widget.clear()
                new_items = list(set(filtered + selected))
                widget.addItems(list(set(filtered + selected)))
                [widget.item(new_items.index(item)).setSelected(True) for item in new_items if item in selected]
                # widget.addItems(list([s for s in selected if s not in widget.items()]) )

            line_search.textChanged.connect(filter_list)

        setup_list_widget(
            self.elementsListWidget, self.elements, self.element_list_handler, self.btnAllElements, self.btnNoneElements, self.lineElementSearch
        )
        setup_list_widget(
            self.compoundsListWidget, self.compounds, self.compound_list_handler, self.btnAllCompounds, self.btnNoneCompounds, self.lineCompoundSearch
        )
        setup_list_widget(
            self.propertiesListWidget,
            self.properties,
            self.property_list_handler,
            self.btnAllProperties,
            self.btnNoneProperties,
            self.linePropertySearch,
        )

        # Constraint List Widget
        self.constraintsModel = QStandardItemModel()
        self.constraintsListWidget.setModel(self.constraintsModel)
        self.constraintsModel.setHorizontalHeaderLabels(["", "", "", "", "OR Group", "Tolerance"])

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

    @property
    def new_constraint(self):
        return [
            self.tableDropdown.currentText(),
            self.columnDropdown.currentText(),
            self.comparisonDropdown.currentText(),
            self.valueField.text(),
            "",
            "",
        ]

    # setter for new_constraint
    @new_constraint.setter
    def new_constraint(self, new_constraint):
        self.tableDropdown.setCurrentText(new_constraint[0])
        self.columnDropdown.setCurrentText(new_constraint[1])
        self.comparisonDropdown.setCurrentText(new_constraint[2])
        self.valueField.setText(str(new_constraint[3]))

    def current_search_spec(self) -> SearchSpec:
        constraints = [
            [self.constraintsModel.item(row, col).text() for col in range(self.constraintsModel.columnCount())]
            for row in range(self.constraintsModel.rowCount())
        ]
        return SearchSpec(
            constraints=constraints,
            elements=[item.text() for item in self.elementsListWidget.selectedItems()],
            compounds=[item.text() for item in self.compoundsListWidget.selectedItems()],
            properties=[item.text() for item in self.propertiesListWidget.selectedItems()],
        )

    def export_to_csv(self):
        df = getattr(self, "df", None)
        if df is None:
            QMessageBox.information(self, "Export to CSV", "Fetch data before exporting.")
            return

        # create a temporary copy of the dataframe to avoid modifying the original
        df_copy = df.copy()
        # remove table names from column headers
        df_copy.columns = [col.split("_")[1] for col in df_copy.columns]
        # remove duplicate columns
        df_copy = df_copy.loc[:, ~df_copy.columns.duplicated()]

        filename, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "", "CSV Files (*.csv)")
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"

        # save the constraints used for this search (as of the last fetch) ahead of the results
        spec = getattr(self, "last_search_spec", None) or self.current_search_spec()
        try:
            write_search_csv(filename, spec, df_copy)
        except OSError as e:
            QMessageBox.critical(self, "Export to CSV", f"Could not write {filename}:\n{e}")

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
                if item.text() in wanted:
                    item.setSelected(True)
            widget.blockSignals(False)
            handler()

        # elements first: selecting elements repopulates the compounds list
        select_items(self.elementsListWidget, spec.elements, self.element_list_handler)
        select_items(self.compoundsListWidget, spec.compounds, self.compound_list_handler)
        select_items(self.propertiesListWidget, spec.properties, self.property_list_handler)

        self.constraintsModel.removeRows(0, self.constraintsModel.rowCount())
        for constraint in spec.constraints:
            self.constraintsModel.appendRow([QStandardItem(value) for value in constraint])
        self.constraintsListWidget.resizeColumnsToContents()

    def build_sql_query(self):
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
            operator = self.constraintsModel.item(row, 2).text()
            value = self.constraintsModel.item(row, 3).text()
            or_group = self.constraintsModel.item(row, 4).text()  # Assuming OR group number is in the fifth column
            tolerance = self.constraintsModel.item(row, 5).text()  # Assuming tolerance is in the sixth column

            # if operator is "=" and tolerance is not empty, change operator to BETWEEN, and add two conditions
            if operator == "=" and tolerance != "":
                operator = "BETWEEN"
                value = f"{float(value) - float(tolerance)} AND {float(value) + float(tolerance)}"
                condition = f"{table}.{column} {operator} {value}"
            else:
                condition = f"{table}.{column} {operator} '{value}'"

            # Group the conditions or add to ungrouped
            if or_group != "":
                or_groups.setdefault(or_group, []).append(condition)
            else:
                ungrouped_clauses.append(condition)

        # Build WHERE clause with OR conditions within groups and AND between groups
        grouped_where_clause = " AND ".join([f"({' OR '.join(conditions)})" for conditions in or_groups.values()])
        ungrouped_where_clause = " AND ".join(ungrouped_clauses)
        where_clause = " AND ".join(filter(None, [grouped_where_clause, ungrouped_where_clause]))

        # Build the JOIN part of the query
        join_clause = """
            compounds
            JOIN elements ON compounds.row_id = elements.row_id
            JOIN property ON compounds.row_id = property.row_id
            JOIN metadata ON compounds.row_id = metadata.row_id
        """

        # Combine everything to form the final query
        query = f"SELECT * FROM {join_clause} WHERE {where_clause}"
        return query

    # For the selected cells in the tableView, create a new constraint for each of the nonzero (and not nan) values and add it to the constraintsModel
    # This is achieved by adding a constraint regardless of the values in the dropdowns and field, and then editing the constraint to match the values in the row
    def add_constraints_from_row(self):
        # Create empty list of new constraints
        new_constraints = []
        # Get the selected cells
        selected_indexes = self.tableView.selectedIndexes()
        # for each selected cell, append the associated column name, the table that column is in, and the value in the cell to the new_constraints list
        for index in selected_indexes:
            column_name = self.model.headerData(index.column(), Qt.Horizontal)
            # set variable "table" to the table name to which the column belongs
            if column_name in lists.elements:
                table = "Elements"
            elif column_name in lists.compounds:
                table = "Compounds"
            elif column_name in lists.properties:
                table = "Property"
            else:
                raise ValueError(f"Column name {column_name} is not in any of the tables")
            value = self.model.item(index.row(), index.column()).text()
            # set variable for tolerance to be 1% of the value
            tolerance = str(float(value) * 0.01)
            new_constraints.append([table, column_name, "=", value, "", tolerance])

        # for each new constraint, add it to the constraintsModel
        for constraint in new_constraints:
            # add a placeholder constraint to the constraintsModel
            self.addConstraint()
            # edit the constraint to match the values in the row, use a for loop through the constraint columns to avoid hardcoding the column numbers
            for i in range(len(constraint)):
                self.constraintsModel.item(self.constraintsModel.rowCount() - 1, i).setText(str(constraint[i]))

    def update_columns(self):
        self.selected_elements = [item.text() for item in self.elementsListWidget.selectedItems()]
        self.selected_compounds = [item.text() for item in self.compoundsListWidget.selectedItems()]
        self.selected_properties = [item.text() for item in self.propertiesListWidget.selectedItems()]
        self.selected_metadata = ["Author", "Year", "NumberCompounds", "id"]
        
        selection = self.tableDropdown.currentText()
        self.columnDropdown.clear()
        self.columnDropdown.addItems(
            {
                "Elements": self.selected_elements,
                "Compounds": self.selected_compounds,
                "Property": self.selected_properties,
                "Metadata": self.selected_metadata,
            }[selection]
        )

    def element_list_handler(self):
        self.selected_elements = [item.text() for item in self.elementsListWidget.selectedItems()]
        self.compounds = lists.compounds
        self.filtered_compounds = filter_compounds_by_elements(lists.compounds, self.selected_elements)
        self.compoundsListWidget.clear()
        self.compoundsListWidget.addItems(self.filtered_compounds)
        self.update_columns()

    def compound_list_handler(self):
        self.selected_compounds = [item.text() for item in self.compoundsListWidget.selectedItems()]
        self.update_columns()

    def property_list_handler(self):
        self.selected_properties = [item.text() for item in self.propertiesListWidget.selectedItems()]
        self.update_columns()

    def fetchData(self):
        self.selected_compounds = [item.text() for item in self.compoundsListWidget.selectedItems()]
        self.unselected_compounds = [c for c in self.compounds if c not in self.selected_compounds]

        self.selected_properties = [item.text() for item in self.propertiesListWidget.selectedItems()]
        self.unselected_properties = [p for p in self.properties if p not in self.selected_properties]

        # Build and execute the SQL query
        sql_query = self.build_sql_query()
        cursor = self.conn.cursor()
        cursor.execute(sql_query)
        query_results = cursor.fetchall()

        # remember the search that produced these results, for export
        self.last_search_spec = self.current_search_spec()

        # Get the total number of results
        self.totalResultsLabel.setText(f"Total Results: {len(query_results)}")

        # Assuming you have column names for the DataFrame (adjust as necessary)
        column_names = [description[0] for description in cursor.description]

        # Create the DataFrame
        self.df = pd.DataFrame(query_results, columns=column_names)

        # Replace 0 with pd.NA
        self.df.replace(0, nan, inplace=True)

        # Drop columns where all values are NA
        self.df.dropna(axis=1, how="all", inplace=True)

        self.df.replace(nan, "", inplace=True)

        # Extract compound columns
        # compound_columns = self.df.columns.get_level_values(0)

        # # Create the Composition string
        # composition = self.df.apply(lambda row: ', '.join(
        #     f"{to_subscript(compound)}: {100*row[compound]:.2f}%" for compound in compound_columns if row[compound] != 0 and "compound" in compound
        # ), axis=1)

        # # Add the Composition column to the DataFrame
        # self.df['Composition'] = composition

        self.column_names = []
        for col in self.df.columns:
            self.column_names.append(col.split("_")[1])

        self.setColumnTitles(self.column_names)
        self.loadData()

        constrained_columns = self.getConstrainedColumns()
        self.highlightDelegate.updateHighlightedColumns(constrained_columns)
        self.tableView.viewport().update()  # Refresh the view

    def getConstrainedColumns(self):
        constrained_column_indices = set()
        for row in range(self.constraintsModel.rowCount()):
            column_name = self.constraintsModel.item(row, 1).text()  # Assuming column name is in the second column
            # Find the index of the column with this name
            for col_index in range(self.model.columnCount()):
                if self.model.headerData(col_index, Qt.Horizontal) == column_name:
                    constrained_column_indices.add(col_index)
                    break  # Stop the loop once the column is found
        return constrained_column_indices

    # Function placeholders for button actions
    def addConstraint(self):
        # Logic to add constraint
        row = []
        for item in self.new_constraint:
            if isinstance(item, (int, float)):
                formatted_item = f"{item:.10g}"
                row.append(QStandardItem(formatted_item))
            else:
                row.append(QStandardItem(str(item)))
        self.constraintsModel.appendRow(row)
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

    def __del__(self):
        # Close the database connection when the window is closed
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
