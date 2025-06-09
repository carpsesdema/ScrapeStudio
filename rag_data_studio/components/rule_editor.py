# rag_data_studio/components/rule_editor.py
"""
UI components for defining and managing scraping rules, including nested rules.
"""
import re
import uuid
from typing import List, Optional

from PySide6.QtWidgets import *
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QBrush, QColor

from ..core.models import ScrapingRule


class VisualElementTargeter(QWidget):
    """A panel for defining a new scraping rule based on a browser selection."""
    rule_created = Signal(ScrapingRule, str)  # Emits rule and parent_id (if it's a sub-rule)
    test_selector_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self.current_selector = ""
        self.current_element_text = ""
        self.current_suggestions = {}
        self.parent_rule_id: Optional[str] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.header = QLabel("🎯 Define New Rule")
        self.header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.header.setStyleSheet("color: #4CAF50; margin: 10px 0;")

        # --- Selection Group ---
        selection_group = QGroupBox("Selected Element")
        selection_layout = QFormLayout(selection_group)
        self.selector_display = QLineEdit()
        self.selector_display.setReadOnly(True)
        self.selector_display.setPlaceholderText("Click an element in the browser...")
        self.element_text_display = QTextEdit()
        self.element_text_display.setReadOnly(True)
        self.element_text_display.setMaximumHeight(60)
        selection_layout.addRow("CSS Selector:", self.selector_display)
        selection_layout.addRow("Element Text:", self.element_text_display)

        # --- Rule Definition Group ---
        rule_def_group = QGroupBox("Rule Definition")
        rule_def_layout = QFormLayout(rule_def_group)
        self.field_name_input = QLineEdit()
        self.field_name_input.setPlaceholderText("e.g., player_name, or player_list")
        rule_def_layout.addRow("Field Name*:", self.field_name_input)

        # --- Extraction Options Group ---
        advanced_group = QGroupBox("Extraction Options")
        advanced_layout = QFormLayout(advanced_group)
        self.extraction_type_combo = QComboBox()
        self.extraction_type_combo.addItems(["text", "attribute", "html", "structured_list"])
        self.attribute_input = QLineEdit()
        self.attribute_input.setPlaceholderText("e.g., href, src")
        self.attribute_input.setEnabled(False)
        self.is_list_check = QCheckBox("Extract all matching elements (as a list)")
        self.is_list_check.setToolTip("For multiple simple values. Implied for 'structured_list'.")
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["string", "number", "boolean", "date", "list_of_strings", "list_of_objects"])
        self.sub_selector_info_label = QLabel(
            "Info: A 'structured_list' is a container for other fields. "
            "Save this rule, then use 'Add Sub-Field' on it.")
        self.sub_selector_info_label.setWordWrap(True)
        self.sub_selector_info_label.setStyleSheet("font-size: 9pt; color: #cccccc;")
        self.sub_selector_info_label.setVisible(False)

        advanced_layout.addRow("Extract How:", self.extraction_type_combo)
        advanced_layout.addRow("Attribute Name:", self.attribute_input)
        advanced_layout.addRow("Data Type:", self.data_type_combo)
        advanced_layout.addRow("", self.is_list_check)
        advanced_layout.addRow(self.sub_selector_info_label)

        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        self.test_btn = QPushButton("🧪 Test Selector")
        self.test_btn.setEnabled(False)
        self.save_btn = QPushButton("💾 Save Rule")
        self.save_btn.setProperty("class", "success")
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.test_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.save_btn)

        layout.addWidget(self.header)
        layout.addWidget(selection_group)
        layout.addWidget(rule_def_group)
        layout.addWidget(advanced_group)
        layout.addLayout(action_layout)
        layout.addStretch()

        # --- Connections ---
        self.extraction_type_combo.currentTextChanged.connect(self.on_extraction_type_changed)
        self.save_btn.clicked.connect(self.save_current_rule)
        self.test_btn.clicked.connect(self.test_current_selector_emit)
        self.is_list_check.toggled.connect(self.on_is_list_toggled)

    def set_mode_for_sub_field(self, parent_rule: ScrapingRule):
        """Pre-configures the form for adding a field to a structured_list."""
        self.parent_rule_id = parent_rule.id
        self.header.setText(f"➕ Add Field to '{parent_rule.name}'")
        self.header.setStyleSheet("color: #FFA726; margin: 10px 0;")  # Orange color for sub-field mode
        # Sub-fields are typically simple extractions within the parent context
        self.extraction_type_combo.clear()
        self.extraction_type_combo.addItems(["text", "attribute", "html"])
        self.extraction_type_combo.setCurrentText("text")
        self.is_list_check.setChecked(False)  # A sub-field extracts one value per parent item
        self.is_list_check.setEnabled(False)
        self.field_name_input.setFocus()

    def reset_mode(self):
        """Resets the form to its default state for defining a new top-level rule."""
        self.parent_rule_id = None
        self.header.setText("🎯 Define New Rule")
        self.header.setStyleSheet("color: #4CAF50; margin: 10px 0;")
        self.extraction_type_combo.clear()
        self.extraction_type_combo.addItems(["text", "attribute", "html", "structured_list"])
        self.is_list_check.setEnabled(True)
        self._clear_form()

    def on_extraction_type_changed(self, extraction_type: str):
        self.attribute_input.setEnabled(extraction_type == "attribute")
        self.sub_selector_info_label.setVisible(extraction_type == "structured_list")
        self.is_list_check.setEnabled(extraction_type != "structured_list")
        if extraction_type == "structured_list":
            self.is_list_check.setChecked(False)  # is_list is implicit
            self.data_type_combo.setCurrentText("list_of_objects")
        else:
            self.on_is_list_toggled(self.is_list_check.isChecked())

    def on_is_list_toggled(self, checked: bool):
        if self.extraction_type_combo.currentText() != "structured_list":
            self.data_type_combo.setCurrentText("list_of_strings" if checked else "string")

    def update_selection(self, selector: str, text: str, suggestions: dict):
        self.current_selector = selector
        self.current_element_text = text
        self.current_suggestions = suggestions

        # Auto-select the 'container' selector if available, it's often more useful
        chosen_suggestion = suggestions.get('container') or suggestions.get('current', {})
        display_selector = chosen_suggestion.get('selector', selector)
        display_text = chosen_suggestion.get('text', text)

        self.selector_display.setText(display_selector)
        self.element_text_display.setText(display_text[:250] + "..." if len(display_text) > 250 else display_text)
        self.save_btn.setEnabled(bool(display_selector))
        self.test_btn.setEnabled(bool(display_selector))

        if not self.field_name_input.text() and text:
            # Auto-suggest name based on text content
            suggested_name = re.sub(r'[^a-zA-Z0-9_]', '', text.lower().replace(" ", "_").replace(":", ""))
            self.field_name_input.setText(suggested_name[:40])

    def save_current_rule(self):
        if not self.selector_display.text() or not self.field_name_input.text():
            QMessageBox.warning(self, "Missing Info", "Please select an element and provide a Field Name.")
            return

        extraction_type = self.extraction_type_combo.currentText()
        is_list_for_rule = (extraction_type == "structured_list") or self.is_list_check.isChecked()

        rule = ScrapingRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            name=self.field_name_input.text().strip(),
            selector=self.selector_display.text().strip(),
            extraction_type=extraction_type,
            attribute_name=self.attribute_input.text().strip() if self.attribute_input.isEnabled() else None,
            is_list=is_list_for_rule,
            data_type=self.data_type_combo.currentText()
        )
        self.rule_created.emit(rule, self.parent_rule_id)
        self.reset_mode()
        QMessageBox.information(self, "Rule Saved", f"Rule '{rule.name}' has been created!")

    def _clear_form(self):
        self.field_name_input.clear()
        self.is_list_check.setChecked(False)
        self.extraction_type_combo.setCurrentIndex(0)
        self.data_type_combo.setCurrentIndex(0)
        self.selector_display.clear()
        self.element_text_display.clear()
        self.save_btn.setEnabled(False)
        self.test_btn.setEnabled(False)

    def test_current_selector_emit(self):
        if not self.selector_display.text():
            QMessageBox.warning(self, "No Selector", "No selector is available to test.")
            return
        self.test_selector_requested.emit({
            "name": self.field_name_input.text() or f"test_rule",
            "selector": self.selector_display.text(),
            "extract_type": self.extraction_type_combo.currentText(),
            "attribute_name": self.attribute_input.text() if self.attribute_input.isEnabled() else None
        })


class RulesManager(QWidget):
    """Manages the tree view of scraping rules and associated actions."""
    rule_selection_changed = Signal(str)  # rule_id
    delete_rule_requested = Signal(str)  # rule_id
    add_sub_rule_requested = Signal(str)  # parent_rule_id

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
        """Clears and rebuilds the entire rule tree from a list of rules."""
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
            item.setToolTip(2, rule.selector)  # Show full selector on hover

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