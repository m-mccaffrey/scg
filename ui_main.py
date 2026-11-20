# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainUsBmlI.ui'
##
## Created by: Qt User Interface Compiler version 6.4.3
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy,
    QSpacerItem, QTableView, QVBoxLayout, QWidget)

from table_view import TableView

class Ui_MainWidget(object):
    def setupUi(self, MainWidget):
        if not MainWidget.objectName():
            MainWidget.setObjectName(u"MainWidget")
        MainWidget.resize(1920, 960)
        self.layout = QVBoxLayout(MainWidget)
        self.layout.setObjectName(u"layout")
        self.top_layout = QHBoxLayout()
        self.top_layout.setObjectName(u"top_layout")
        self.gridLayout_2 = QGridLayout()
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(10, 0, 10, -1)
        self.elementsListWidget = QListWidget(MainWidget)
        self.elementsListWidget.setObjectName(u"elementsListWidget")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.elementsListWidget.sizePolicy().hasHeightForWidth())
        self.elementsListWidget.setSizePolicy(sizePolicy)
        self.elementsListWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        self.gridLayout_2.addWidget(self.elementsListWidget, 1, 0, 1, 2)

        self.btnAllElements = QPushButton(MainWidget)
        self.btnAllElements.setObjectName(u"btnAllElements")

        self.gridLayout_2.addWidget(self.btnAllElements, 2, 0, 1, 1)

        self.btnNoneElements = QPushButton(MainWidget)
        self.btnNoneElements.setObjectName(u"btnNoneElements")

        self.gridLayout_2.addWidget(self.btnNoneElements, 2, 1, 1, 1)

        self.lineElementSearch = QLineEdit(MainWidget)
        self.lineElementSearch.setObjectName(u"lineElementSearch")

        self.gridLayout_2.addWidget(self.lineElementSearch, 0, 0, 1, 2)


        self.top_layout.addLayout(self.gridLayout_2)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(10, -1, 10, -1)
        self.btnAllCompounds = QPushButton(MainWidget)
        self.btnAllCompounds.setObjectName(u"btnAllCompounds")

        self.gridLayout.addWidget(self.btnAllCompounds, 2, 0, 1, 1)

        self.btnNoneCompounds = QPushButton(MainWidget)
        self.btnNoneCompounds.setObjectName(u"btnNoneCompounds")

        self.gridLayout.addWidget(self.btnNoneCompounds, 2, 1, 1, 1)

        self.compoundsListWidget = QListWidget(MainWidget)
        self.compoundsListWidget.setObjectName(u"compoundsListWidget")
        sizePolicy.setHeightForWidth(self.compoundsListWidget.sizePolicy().hasHeightForWidth())
        self.compoundsListWidget.setSizePolicy(sizePolicy)
        self.compoundsListWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        self.gridLayout.addWidget(self.compoundsListWidget, 1, 0, 1, 2)

        self.lineCompoundSearch = QLineEdit(MainWidget)
        self.lineCompoundSearch.setObjectName(u"lineCompoundSearch")

        self.gridLayout.addWidget(self.lineCompoundSearch, 0, 0, 1, 2)


        self.top_layout.addLayout(self.gridLayout)

        self.gridLayout_3 = QGridLayout()
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setContentsMargins(10, -1, 10, -1)
        self.btnAllProperties = QPushButton(MainWidget)
        self.btnAllProperties.setObjectName(u"btnAllProperties")

        self.gridLayout_3.addWidget(self.btnAllProperties, 2, 0, 1, 1)

        self.propertiesListWidget = QListWidget(MainWidget)
        self.propertiesListWidget.setObjectName(u"propertiesListWidget")
        sizePolicy.setHeightForWidth(self.propertiesListWidget.sizePolicy().hasHeightForWidth())
        self.propertiesListWidget.setSizePolicy(sizePolicy)
        self.propertiesListWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        self.gridLayout_3.addWidget(self.propertiesListWidget, 1, 0, 1, 2)

        self.btnNoneProperties = QPushButton(MainWidget)
        self.btnNoneProperties.setObjectName(u"btnNoneProperties")

        self.gridLayout_3.addWidget(self.btnNoneProperties, 2, 1, 1, 1)

        self.linePropertySearch = QLineEdit(MainWidget)
        self.linePropertySearch.setObjectName(u"linePropertySearch")

        self.gridLayout_3.addWidget(self.linePropertySearch, 0, 0, 1, 2)


        self.top_layout.addLayout(self.gridLayout_3)

        self.constraint_builder_layout = QGridLayout()
        self.constraint_builder_layout.setObjectName(u"constraint_builder_layout")
        self.tableDropdown = QComboBox(MainWidget)
        self.tableDropdown.addItem("")
        self.tableDropdown.addItem("")
        self.tableDropdown.addItem("")
        self.tableDropdown.addItem("")
        self.tableDropdown.setObjectName(u"tableDropdown")

        self.constraint_builder_layout.addWidget(self.tableDropdown, 2, 1, 1, 1)

        self.columnDropdown = QComboBox(MainWidget)
        self.columnDropdown.addItem("")
        self.columnDropdown.setObjectName(u"columnDropdown")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.columnDropdown.sizePolicy().hasHeightForWidth())
        self.columnDropdown.setSizePolicy(sizePolicy1)
        self.columnDropdown.setMinimumSize(QSize(150, 0))
        self.columnDropdown.setMaximumSize(QSize(150, 16777215))

        self.constraint_builder_layout.addWidget(self.columnDropdown, 2, 2, 1, 1)

        self.comparisonDropdown = QComboBox(MainWidget)
        self.comparisonDropdown.addItem("")
        self.comparisonDropdown.addItem("")
        self.comparisonDropdown.addItem("")
        self.comparisonDropdown.addItem("")
        self.comparisonDropdown.addItem("")
        self.comparisonDropdown.setObjectName(u"comparisonDropdown")

        self.constraint_builder_layout.addWidget(self.comparisonDropdown, 2, 3, 1, 1)

        self.valueField = QLineEdit(MainWidget)
        self.valueField.setObjectName(u"valueField")
        sizePolicy1.setHeightForWidth(self.valueField.sizePolicy().hasHeightForWidth())
        self.valueField.setSizePolicy(sizePolicy1)
        self.valueField.setMinimumSize(QSize(100, 0))
        self.valueField.setMaximumSize(QSize(100, 16777215))

        self.constraint_builder_layout.addWidget(self.valueField, 2, 4, 1, 1)

        self.addButton = QPushButton(MainWidget)
        self.addButton.setObjectName(u"addButton")

        self.constraint_builder_layout.addWidget(self.addButton, 2, 5, 1, 1)

        self.removeButton = QPushButton(MainWidget)
        self.removeButton.setObjectName(u"removeButton")

        self.constraint_builder_layout.addWidget(self.removeButton, 2, 6, 1, 1)

        self.constraintsListWidget = QTableView(MainWidget)
        self.constraintsListWidget.setObjectName(u"constraintsListWidget")
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.constraintsListWidget.sizePolicy().hasHeightForWidth())
        self.constraintsListWidget.setSizePolicy(sizePolicy2)

        self.constraint_builder_layout.addWidget(self.constraintsListWidget, 1, 1, 1, 7)


        self.top_layout.addLayout(self.constraint_builder_layout)


        self.layout.addLayout(self.top_layout)

        self.tableView = TableView(MainWidget)
        self.tableView.setObjectName(u"tableView")

        self.layout.addWidget(self.tableView)

        self.bottom_layout = QGridLayout()
        self.bottom_layout.setObjectName(u"bottom_layout")
        self.bottom_layout.setHorizontalSpacing(20)
        self.bottom_layout.setContentsMargins(20, -1, 20, -1)
        self.export_button = QPushButton(MainWidget)
        self.export_button.setObjectName(u"export_button")

        self.bottom_layout.addWidget(self.export_button, 2, 7, 1, 1)

        self.pageLabel = QLabel(MainWidget)
        self.pageLabel.setObjectName(u"pageLabel")

        self.bottom_layout.addWidget(self.pageLabel, 1, 5, 1, 1)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.bottom_layout.addItem(self.horizontalSpacer, 1, 0, 1, 1)

        self.btnImport = QPushButton(MainWidget)
        self.btnImport.setObjectName(u"btnImport")

        self.bottom_layout.addWidget(self.btnImport, 2, 6, 1, 1)

        self.add_constraints_from_row_button = QPushButton(MainWidget)
        self.add_constraints_from_row_button.setObjectName(u"add_constraints_from_row_button")

        self.bottom_layout.addWidget(self.add_constraints_from_row_button, 2, 5, 1, 1)

        self.prevPageButton = QPushButton(MainWidget)
        self.prevPageButton.setObjectName(u"prevPageButton")

        self.bottom_layout.addWidget(self.prevPageButton, 1, 6, 1, 1)

        self.nextPageButton = QPushButton(MainWidget)
        self.nextPageButton.setObjectName(u"nextPageButton")

        self.bottom_layout.addWidget(self.nextPageButton, 1, 7, 1, 1)

        self.load_button = QPushButton(MainWidget)
        self.load_button.setObjectName(u"load_button")

        self.bottom_layout.addWidget(self.load_button, 2, 4, 1, 1)

        self.totalResultsLabel = QLabel(MainWidget)
        self.totalResultsLabel.setObjectName(u"totalResultsLabel")

        self.bottom_layout.addWidget(self.totalResultsLabel, 1, 4, 1, 1)


        self.layout.addLayout(self.bottom_layout)


        self.retranslateUi(MainWidget)

        QMetaObject.connectSlotsByName(MainWidget)
    # setupUi

    def retranslateUi(self, MainWidget):
        MainWidget.setWindowTitle(QCoreApplication.translate("MainWidget", u"Interface", None))
        self.btnAllElements.setText(QCoreApplication.translate("MainWidget", u"All", None))
        self.btnNoneElements.setText(QCoreApplication.translate("MainWidget", u"None", None))
        self.btnAllCompounds.setText(QCoreApplication.translate("MainWidget", u"All", None))
        self.btnNoneCompounds.setText(QCoreApplication.translate("MainWidget", u"None", None))
        self.btnAllProperties.setText(QCoreApplication.translate("MainWidget", u"All", None))
        self.btnNoneProperties.setText(QCoreApplication.translate("MainWidget", u"None", None))
        self.tableDropdown.setItemText(0, QCoreApplication.translate("MainWidget", u"Elements", None))
        self.tableDropdown.setItemText(1, QCoreApplication.translate("MainWidget", u"Compounds", None))
        self.tableDropdown.setItemText(2, QCoreApplication.translate("MainWidget", u"Property", None))
        self.tableDropdown.setItemText(3, QCoreApplication.translate("MainWidget", u"Metadata", None))

        self.columnDropdown.setItemText(0, "")

        self.comparisonDropdown.setItemText(0, QCoreApplication.translate("MainWidget", u"<", None))
        self.comparisonDropdown.setItemText(1, QCoreApplication.translate("MainWidget", u">", None))
        self.comparisonDropdown.setItemText(2, QCoreApplication.translate("MainWidget", u"=", None))
        self.comparisonDropdown.setItemText(3, QCoreApplication.translate("MainWidget", u"<=", None))
        self.comparisonDropdown.setItemText(4, QCoreApplication.translate("MainWidget", u">=", None))

        self.addButton.setText(QCoreApplication.translate("MainWidget", u"Add", None))
        self.removeButton.setText(QCoreApplication.translate("MainWidget", u"Remove", None))
        self.export_button.setText(QCoreApplication.translate("MainWidget", u"Export to CSV", None))
        self.btnImport.setText(QCoreApplication.translate("MainWidget", u"Import From CSV", None))
        self.add_constraints_from_row_button.setText(QCoreApplication.translate("MainWidget", u"Add Constraints From Selected Values", None))
        self.prevPageButton.setText(QCoreApplication.translate("MainWidget", u"Previous Page", None))
        self.nextPageButton.setText(QCoreApplication.translate("MainWidget", u"Next Page", None))
        self.load_button.setText(QCoreApplication.translate("MainWidget", u"Fetch Data", None))
    # retranslateUi

