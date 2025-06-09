# rag_data_studio/components/dialogs.py
"""
Custom dialog boxes used in the Data Extractor Studio.
"""
import json
from typing import List, Dict, Any

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont


class TestResultsDialog(QDialog):
    """A dialog to show the results of testing selectors against a live URL."""
    def __init__(self, results: Dict[str, Any], parent=None, test_url="N/A"):
        super().__init__(parent)
        self.setWindowTitle(f"Selector Test Results")
        self.setModal(True)
        self.resize(850, 600)
        self.init_ui(results, test_url)

    def init_ui(self, results: Dict[str, Any], test_url: str):
        layout = QVBoxLayout(self)

        url_label = QLabel(f"<b>Test URL:</b> {test_url}")
        url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(url_label)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Rule Name", "Status", "Found", "Sample Values (up to 5)"])
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(True)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        if "error" in results:
            self.results_table.setRowCount(1)
            self.results_table.setColumnCount(1)
            error_item = QTableWidgetItem(f"Failed to fetch or process URL:\n{results['error']}")
            error_item.setForeground(QColor("red"))
            self.results_table.setItem(0, 0, error_item)
        else:
            self.results_table.setRowCount(len(results))
            for row, (name, result_data) in enumerate(results.items()):
                # Rule Name
                self.results_table.setItem(row, 0, QTableWidgetItem(name))

                # Status
                status_text = "✅ Success" if result_data.get('success') else "❌ Failed"
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                if result_data.get('success'):
                    status_item.setBackground(QColor("#2E7D32"))
                else:
                    status_item.setBackground(QColor("#C62828"))
                    status_item.setToolTip(result_data.get('error', 'No specific error message.'))
                self.results_table.setItem(row, 1, status_item)

                # Found Count
                count_item = QTableWidgetItem(str(result_data.get('found_count', 0)))
                count_item.setTextAlignment(Qt.AlignCenter)
                self.results_table.setItem(row, 2, count_item)

                # Sample Values
                sample_text = "\n\n".join(result_data.get('sample_values', []))
                sample_item = QTableWidgetItem(sample_text)
                sample_item.setFont(QFont("Consolas", 9))
                self.results_table.setItem(row, 3, sample_item)

        self.results_table.resizeColumnsToContents()
        self.results_table.resizeRowsToContents()
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        layout.addWidget(self.results_table)
        layout.addWidget(close_btn, 0, Qt.AlignRight)