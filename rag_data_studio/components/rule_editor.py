# rag_data_studio/components/rule_editor.py
"""
UI components for defining and managing scraping rules.
REBUILT for reliable Auto-Detect Table feature.
"""
import uuid
import re
from typing import List, Optional

from PySide6.QtWidgets import *
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QBrush, QColor

from ..core.models import ScrapingRule


class VisualElementTargeter(QWidget):
    """A panel for defining a new scraping rule based on a browser selection."""
    rule_created = Signal(ScrapingRule, str)
    batch_rules_created = Signal(list)

    def __init__(self):
        super().__init__()
        self.current_selector = ""
        self.last_table_info = {}
        self.parent_rule_id: Optional[str] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.header = QLabel("🎯 Define New Rule")
        self.header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.header.setStyleSheet("color: #4CAF50; margin: 10px 0;")

        selection_group = QGroupBox("Selected Element")
        selection_layout = QFormLayout(selection_group)
        self.selector_display = QLineEdit()
        self.selector_display.setPlaceholderText("Click an element in the browser...")
        self.element_text_display = QTextEdit()
        self.element_text_display.setReadOnly(True)
        self.element_text_display.setMaximumHeight(60)
        selection_layout.addRow("CSS Selector:", self.selector_display)
        selection_layout.addRow("Element Text:", self.element_text_display)

        rule_def_group = QGroupBox("Rule Definition")
        rule_def_layout = QFormLayout(rule_def_group)
        self.field_name_input = QLineEdit()
        self.field_name_input.setPlaceholderText("e.g., player_name, or player_list")
        rule_def_layout.addRow("Field Name*:", self.field_name_input)

        self.auto_table_btn = QPushButton("🪄 Auto-Detect Table")
        self.auto_table_btn.setToolTip("Click a cell, then this button to auto-detect the whole table structure.")
        self.auto_table_btn.setEnabled(False)
        rule_def_layout.addRow(self.auto_table_btn)

        advanced_group = QGroupBox("Extraction Options")
        advanced_layout = QFormLayout(advanced_group)
        self.extraction_type_combo = QComboBox()
        self.extraction_type_combo.addItems(["text", "attribute", "html", "structured_list"])
        self.attribute_input = QLineEdit()
        self.attribute_input.setPlaceholderText("e.g., href, src")
        self.attribute_input.setEnabled(False)
        self.is_list_check = QCheckBox("Extract all matching elements (as a list)")
        advanced_layout.addRow("Extract How:", self.extraction_type_combo)
        advanced_layout.addRow("Attribute Name:", self.attribute_input)
        advanced_layout.addRow("", self.is_list_check)

        action_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Rule")
        self.save_btn.setProperty("class", "success")
        self.save_btn.setEnabled(False)
        action_layout.addStretch()
        action_layout.addWidget(self.save_btn)

        layout.addWidget(self.header)
        layout.addWidget(selection_group)
        layout.addWidget(rule_def_group)
        layout.addWidget(advanced_group)
        layout.addLayout(action_layout)
        layout.addStretch()

        self.save_btn.clicked.connect(self.save_current_rule)
        self.auto_table_btn.clicked.connect(self.on_auto_detect_table)

    def on_auto_detect_table(self):
        if not self.last_table_info or not self.last_table_info.get('is_in_table'):
            QMessageBox.warning(self, "Not a Table", "The last clicked element was not inside a valid table.")
            return

        headers = self.last_table_info.get('headers', [])
        if not headers:
            QMessageBox.warning(self, "No Headers Found", "Could not find table headers (<th> elements).")
            return

        row_selector = self.last_table_info.get('row_selector')
        if not row_selector:
            QMessageBox.warning(self, "Could not find row selector", "Could not determine the selector for table rows.")
            return
        # Generalize the row selector to get all rows, not just the one clicked
        all_rows_selector = re.sub(r':nth-of-type\(\d+\)$', '', row_selector)

        main_rule_name = self.field_name_input.text().strip() or "table_data"
        main_rule = ScrapingRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            name=main_rule_name,
            selector=all_rows_selector,
            extraction_type="structured_list",
            is_list=True,
            data_type="list_of_objects"
        )

        for i, header_text in enumerate(headers):
            field_name = re.sub(r'[^a-zA-Z0-9_]', '', header_text.lower().replace(" ", "_")) or f"column_{i + 1}"
            sub_rule = ScrapingRule(
                id=f"rule_{uuid.uuid4().hex[:8]}",
                name=field_name,
                selector=f"td:nth-of-type({i + 1}), th:nth-of-type({i + 1})",  # Handle rows with th or td
                extraction_type="text"
            )
            main_rule.sub_selectors.append(sub_rule)

        self.batch_rules_created.emit([main_rule])
        QMessageBox.information(self, "Success!", f"Table '{main_rule_name}' with {len(headers)} columns detected!")
        self.reset_mode()

    def update_selection(self, selector: str, text: str):
        self.current_selector = selector
        self.selector_display.setText(selector)
        self.element_text_display.setText(text)
        self.save_btn.setEnabled(True)

        # Asynchronously ask the browser for more details about this element
        self.window().browser.get_element_info(selector, self.on_element_info_received)

        if not self.field_name_input.text() and text:
            suggested_name = re.sub(r'[^a-zA-Z0-9_]', '', text.lower().replace(" ", "_"))
            self.field_name_input.setText(suggested_name[:40])

    def on_element_info_received(self, info: Optional[dict]):
        if info and info.get('is_in_table'):
            self.last_table_info = info
            self.auto_table_btn.setEnabled(True)
            # Pre-fill field name for convenience
            if not self.field_name_input.text():
                self.field_name_input.setText("scraped_table")
        else:
            self.last_table_info = {}
            self.auto_table_btn.setEnabled(False)

    def save_current_rule(self):
        if not self.current_selector or not self.field_name_input.text():
            QMessageBox.warning(self, "Missing Info", "Please select an element and provide a Field Name.")
            return

        rule = ScrapingRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            name=self.field_name_input.text().strip(),
            selector=self.current_selector,
            extraction_type=self.extraction_type_combo.currentText(),
            attribute_name=self.attribute_input.text().strip() if self.attribute_input.isEnabled() else None,
            is_list=self.is_list_check.isChecked()
        )
        self.rule_created.emit(rule, self.parent_rule_id)
        self.reset_mode()
        QMessageBox.information(self, "Rule Saved", f"Rule '{rule.name}' has been created!")

    def reset_mode(self):
        self.parent_rule_id = None
        self.header.setText("🎯 Define New Rule")
        self.header.setStyleSheet("color: #4CAF50; margin: 10px 0;")
        self._clear_form()

    def _clear_form(self):
        self.field_name_input.clear()
        self.selector_display.clear()
        self.element_text_display.clear()
        self.save_btn.setEnabled(False)
        self.auto_table_btn.setEnabled(False)
        self.last_table_info = {}
        self.current_selector = ""

    def set_mode_for_sub_field(self, parent_rule: ScrapingRule):
        self.parent_rule_id = parent_rule.id
        self.header.setText(f"➕ Add Field to '{parent_rule.name}'")
        self.header.setStyleSheet("color: #FFA726; margin: 10px 0;")
        self.field_name_input.setFocus()


# Keeping RulesManager the same as it was already correct
class RulesManager(QWidget):
    """Manages the tree view of scraping rules and associated actions."""
    rule_selection_changed = Signal(str)
    delete_rule_requested = Signal(str)
    add_sub_rule_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel("📋 Defined Rules")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet("color: #4CAF50; margin: 10px 0;")

        self.rules_tree = QTreeWidget()
        self.rules_tree.setColumnCount(3)
        self.rules_tree.setHeaderLabels(["Field Name", "Extract Type", "Selector"])
        self.rules_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.rules_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.rules_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)

        rule_actions_layout = QHBoxLayout()
        self.add_sub_rule_btn = QPushButton("➕ Add Sub-Field")
        self.add_sub_rule_btn.setToolTip("Add a field to a 'structured_list' rule.")
        self.add_sub_rule_btn.setEnabled(False)
        self.delete_rule_btn = QPushButton("🗑️ Delete Selected")
        self.delete_rule_btn.setEnabled(False)

        rule_actions_layout.addStretch()
        rule_actions_layout.addWidget(self.add_sub_rule_btn)
        rule_actions_layout.addWidget(self.delete_rule_btn)

        layout.addWidget(header)
        layout.addWidget(self.rules_tree)
        layout.addLayout(rule_actions_layout)

        self.rules_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.add_sub_rule_btn.clicked.connect(self._request_add_sub_rule)
        self.delete_rule_btn.clicked.connect(self._request_delete_selected_rule)

    def _on_selection_changed(self):
        selected_items = self.rules_tree.selectedItems()
        if not selected_items:
            self.add_sub_rule_btn.setEnabled(False)
            self.delete_rule_btn.setEnabled(False)
            return

        selected_item = selected_items[0]
        rule_id = selected_item.data(0, Qt.UserRole)
        is_structured_list = selected_item.text(1) == "structured_list"

        self.add_sub_rule_btn.setEnabled(is_structured_list)
        self.delete_rule_btn.setEnabled(True)
        if rule_id: self.rule_selection_changed.emit(rule_id)

    def _request_add_sub_rule(self):
        if self.rules_tree.selectedItems():
            self.add_sub_rule_requested.emit(self.rules_tree.selectedItems()[0].data(0, Qt.UserRole))

    def _request_delete_selected_rule(self):
        if self.rules_tree.selectedItems():
            self.delete_rule_requested.emit(self.rules_tree.selectedItems()[0].data(0, Qt.UserRole))

    def set_rules(self, rules: List[ScrapingRule]):
        self.rules_tree.clear()

        def add_item_to_tree(rule, parent_widget):
            item = QTreeWidgetItem(parent_widget)
            item.setText(0, rule.name)
            extract_display = rule.extraction_type
            if rule.extraction_type == "attribute":
                extract_display += f" ({rule.attribute_name or 'N/A'})"
            item.setText(1, extract_display)
            item.setText(2, rule.selector)
            item.setData(0, Qt.UserRole, rule.id)
            item.setToolTip(2, rule.selector)

            if rule.extraction_type == "structured_list":
                item.setForeground(0, QBrush(QColor("#4CAF50")))
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
                item.setExpanded(True)

            for sub_rule in rule.sub_selectors:
                add_item_to_tree(sub_rule, item)

        for rule in rules:
            add_item_to_tree(rule, self.rules_tree)

        self.rules_tree.resizeColumnToContents(0)
        self.rules_tree.resizeColumnToContents(1)