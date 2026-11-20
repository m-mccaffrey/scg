from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtWidgets import QTableView 

class FloatDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def displayText(self, value, locale):
        if isinstance(value, (int, float)):
            return f"{value:.5g}"
        else:
            return str(value)

# Overloaded QTableView class to display floats with 5 significant figures but retain their original values
class TableView(QTableView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setItemDelegate(FloatDelegate(self))