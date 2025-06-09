# rag_data_studio/main_application.py
"""
RAG Data Studio - Main Application Window
The central hub that orchestrates all UI components and backend interactions.
"""
import sys
import yaml
import tempfile
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# Import new, modular components
from .core.models import ProjectConfig, ScrapingRule
from .components.project_panel import ProjectManager, ProjectDialog
from .components.browser import InteractiveBrowser
from .components.rule_editor import VisualElementTargeter, RulesManager
from .components.dialogs import TestResultsDialog
from .integration.backend_bridge import BackendWorker

# Import backend and storage components
from scraper.searcher import run_pipeline, run_pipeline_on_html
from storage.database_inserter import DatabaseInserter
from utils.logger import setup_logger


# It's good practice to have the theme as a separate function or in a separate file
def load_dark_theme():
    return """
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 10pt;
    }
    QMainWindow, QDialog {
        background-color: #1e1e1e;
    }
    QGroupBox {
        font-weight: bold;
        border: 1px solid #404040;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        background-color: #2d2d2d;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
        color: #4CAF50;
    }
    QPushButton {
        background-color: #404040; border: 1px solid #606060;
        border-radius: 6px; padding: 8px 16px; font-weight: bold;
    }
    QPushButton:hover { background-color: #505050; border-color: #4CAF50; }
    QPushButton:pressed { background-color: #303030; }
    QPushButton:disabled { background-color: #2a2a2a; color: #666; }
    QPushButton[class="success"] { background-color: #4CAF50; border-color: #45a049; }
    QPushButton[class="success"]:hover { background-color: #45a049; }
    QCheckBox { spacing: 5px; }
    QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px; }
    QCheckBox::indicator:checked { background-color: #4CAF50; border-color: #66BB6A; }
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
        background-color: #3a3a3a; border: 1px solid #555555;
        border-radius: 6px; padding: 6px; selection-background-color: #4CAF50;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #4CAF50; }
    QComboBox::drop-down { border: none; background-color: #505050; }
    QComboBox QAbstractItemView { background-color: #3a3a3a; border: 1px solid #555555; }
    QTableWidget, QTreeWidget {
        background-color: #2a2a2a; alternate-background-color: #343434;
        gridline-color: #404040; border: 1px solid #404040;
    }
    QHeaderView::section {
        background-color: #404040; padding: 8px; border: 1px solid #555555; font-weight: bold;
    }
    QListWidget { background-color: #2a2a2a; border: 1px solid #555555; }
    QListWidget::item:selected { background-color: #4CAF50; }
    QStatusBar { border-top: 1px solid #404040; }
    QSplitter::handle { background-color: #404040; }
    QScrollBar:vertical { border: none; background: #2a2a2a; width: 10px; }
    QScrollBar::handle:vertical { background: #505050; min-height: 20px; border-radius: 5px; }
    QScrollBar:horizontal { border: none; background: #2a2a2a; height: 10px; }
    QScrollBar::handle:horizontal { background: #505050; min-width: 20px; border-radius: 5px; }
    """


class ScrapeRunner(QObject):
    """Worker to run the full scrape pipeline in a separate thread."""
    finished = Signal(list, dict)  # Emits results and metrics
    error = Signal(str)

    def __init__(self, config_path: str, html_content: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.html_content = html_content

    def run(self):
        try:
            if self.html_content:
                results, metrics = run_pipeline_on_html(self.config_path, self.html_content)
            else:
                results, metrics = run_pipeline(self.config_path)
            self.finished.emit(results, metrics)
        except Exception as e:
            self.error.emit(str(e))


class RAGDataStudio(QMainWindow):
    """Main Application Window"""

    def __init__(self):
        super().__init__()
        self.current_project: Optional[ProjectConfig] = None
        self.backend_thread = None
        self.backend_worker = None
        self.logger = setup_logger()
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Scrape Studio - Visual Scraper Builder")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet(load_dark_theme())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_splitter = QSplitter(Qt.Horizontal)

        # Left Panel
        self.project_manager = ProjectManager()
        self.project_manager.setMinimumWidth(250)
        self.project_manager.setMaximumWidth(400)
        main_splitter.addWidget(self.project_manager)

        # Center Panel
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL to analyze and press Enter...")
        self.load_btn = QPushButton("🌐 Load")
        self.selector_btn = QPushButton("🎯 Target Elements")
        self.selector_btn.setProperty("class", "success")
        self.selector_btn.setCheckable(True)
        toolbar_layout.addWidget(self.url_input)
        toolbar_layout.addWidget(self.load_btn)
        toolbar_layout.addWidget(self.selector_btn)
        self.browser = InteractiveBrowser()
        center_layout.addLayout(toolbar_layout)
        center_layout.addWidget(self.browser)
        main_splitter.addWidget(center_widget)

        # Right Panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_splitter = QSplitter(Qt.Vertical)
        self.element_targeter = VisualElementTargeter()
        self.rules_manager = RulesManager()
        right_splitter.addWidget(self.element_targeter)
        right_splitter.addWidget(self.rules_manager)
        right_splitter.setSizes([450, 350])

        # Actions Group
        global_actions_group = QGroupBox("Project Actions")
        global_actions_layout = QVBoxLayout(global_actions_group)

        self.scrape_from_browser_checkbox = QCheckBox("Scrape from current browser view")
        self.scrape_from_browser_checkbox.setToolTip(
            "If checked, the scraper will use the exact HTML currently visible in the browser.\n"
            "Useful for pages that change content with JavaScript after loading."
        )

        buttons_layout = QHBoxLayout()
        self.test_all_btn = QPushButton("🧪 Test All Rules")
        self.export_config_btn = QPushButton("💾 Export to YAML")
        self.run_scrape_btn = QPushButton("🚀 Run Full Scrape")
        self.run_scrape_btn.setProperty("class", "success")
        buttons_layout.addWidget(self.test_all_btn)
        buttons_layout.addWidget(self.export_config_btn)
        buttons_layout.addWidget(self.run_scrape_btn)

        global_actions_layout.addWidget(self.scrape_from_browser_checkbox)
        global_actions_layout.addLayout(buttons_layout)

        right_layout.addWidget(right_splitter)
        right_layout.addWidget(global_actions_group)
        right_widget.setMinimumWidth(350)
        right_widget.setMaximumWidth(500)
        main_splitter.addWidget(right_widget)

        main_splitter.setSizes([300, 900, 400])
        main_layout.addWidget(main_splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Create or select a project to begin.")

    def connect_signals(self):
        self.project_manager.project_selected.connect(self.load_project)
        self.project_manager.new_project_requested.connect(self.create_new_project)
        self.url_input.returnPressed.connect(self.load_page)
        self.load_btn.clicked.connect(self.load_page)
        self.selector_btn.toggled.connect(self.toggle_selector_mode)
        self.browser.element_selected.connect(self.element_targeter.update_selection)
        self.element_targeter.rule_created.connect(self.add_rule_to_project)
        self.element_targeter.batch_rules_created.connect(self.add_batch_rules_to_project)
        self.rules_manager.delete_rule_requested.connect(self.delete_rule_from_project)
        self.rules_manager.add_sub_rule_requested.connect(self.set_targeter_for_sub_rule)

        # The "Test Selector" button was removed from the GUI, so we remove its connection.
        # self.element_targeter.test_selector_requested.connect(self.test_single_selector) # <<< THIS IS THE BUG. REMOVING.

        self.test_all_btn.clicked.connect(self.test_all_rules)
        self.export_config_btn.clicked.connect(self.export_project_config)
        self.run_scrape_btn.clicked.connect(self.run_full_scrape)

    def create_new_project(self):
        dialog = ProjectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_project = dialog.get_project_config()
            self.project_manager.add_or_update_project(new_project)
            self.load_project(new_project)

    def load_project(self, project: ProjectConfig):
        self.current_project = project
        self.rules_manager.set_rules(project.scraping_rules)
        self.element_targeter.reset_mode()
        if project.target_websites: self.url_input.setText(project.target_websites[0])
        self.status_bar.showMessage(f"Loaded project: {project.name}")

    def save_current_project(self):
        if self.current_project:
            self.current_project.updated_at = QDateTime.currentDateTime().toString(Qt.ISODate)
            self.project_manager.add_or_update_project(self.current_project)
            self.status_bar.showMessage(f"Project '{self.current_project.name}' saved.", 3000)

    def add_rule_to_project(self, rule: ScrapingRule, parent_id: Optional[str]):
        if not self.current_project: return
        if parent_id:
            parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_id)
            if parent_rule: parent_rule.sub_selectors.append(rule)
        else:
            self.current_project.scraping_rules.append(rule)
        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()

    def add_batch_rules_to_project(self, rules: List[ScrapingRule]):
        if not self.current_project: return
        self.current_project.scraping_rules.extend(rules)
        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()
        self.status_bar.showMessage(f"Added {len(rules)} new rules from auto-detect.", 3000)

    def delete_rule_from_project(self, rule_id: str):
        if not self.current_project: return
        reply = QMessageBox.question(self, "Delete Rule", "Delete this rule and all its sub-rules?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No: return

        def find_and_remove(rules: List[ScrapingRule], r_id: str) -> bool:
            for i, rule in enumerate(rules):
                if rule.id == r_id: del rules[i]; return True
                if find_and_remove(rule.sub_selectors, r_id): return True
            return False

        if find_and_remove(self.current_project.scraping_rules, rule_id):
            self.rules_manager.set_rules(self.current_project.scraping_rules)
            self.save_current_project()

    def set_targeter_for_sub_rule(self, parent_rule_id: str):
        if not self.current_project: return
        parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_rule_id)
        if parent_rule:
            self.element_targeter.set_mode_for_sub_field(parent_rule)
            self.status_bar.showMessage(f"Select an element to add a sub-field to '{parent_rule.name}'.")

    def _find_rule_by_id(self, rules: List[ScrapingRule], r_id: str) -> Optional[ScrapingRule]:
        for rule in rules:
            if rule.id == r_id: return rule
            found = self._find_rule_by_id(rule.sub_selectors, r_id)
            if found: return found
        return None

    def load_page(self):
        url = self.url_input.text().strip()
        if not url: return
        if not url.startswith(('http://', 'https://')): url = 'https://' + url
        self.browser.load(QUrl(url))
        self.status_bar.showMessage(f"Loading: {url}")

    def toggle_selector_mode(self, checked):
        if checked:
            self.browser.enable_selector_mode()
        else:
            self.browser.disable_selector_mode()
        self.selector_btn.setText("❌ Stop Targeting" if checked else "🎯 Target Elements")
        if not checked: self.element_targeter.reset_mode()
        self.status_bar.showMessage(f"Targeting mode {'enabled' if checked else 'disabled'}.")

    def _execute_backend_task(self, task_name: str, **kwargs):
        self.backend_thread = QThread()
        if task_name == 'test_selectors':
            worker = BackendWorker(self.logger)
            worker.moveToThread(self.backend_thread)
            worker.test_results_ready.connect(self.on_test_results_ready)
            worker.error_occurred.connect(self.on_backend_error)
            self.backend_thread.started.connect(lambda: worker.test_selectors_on_url(kwargs['url'], kwargs['rules']))
        elif task_name == 'run_scrape':
            worker = ScrapeRunner(kwargs['config_path'], kwargs.get('html_content'))
            worker.moveToThread(self.backend_thread)
            worker.finished.connect(self.on_scrape_finished)
            worker.error.connect(self.on_backend_error)
            self.backend_thread.started.connect(worker.run)

        self.backend_thread.finished.connect(self.backend_thread.deleteLater)
        self.backend_thread.start()

    def test_all_rules(self):
        if not self.current_project or not self.browser.url().isValid(): return
        url = self.browser.url().toString()
        rules = [r.to_dict() for r in self.current_project.scraping_rules]
        self.status_bar.showMessage(f"Testing all {len(rules)} rules on {url}...")
        self._execute_backend_task('test_selectors', url=url, rules=rules)

    def on_test_results_ready(self, results: dict):
        if self.backend_thread: self.backend_thread.quit()
        dialog = TestResultsDialog(results, self, test_url=self.browser.url().toString())
        dialog.exec()

    def on_backend_error(self, error_message: str):
        if self.backend_thread: self.backend_thread.quit()
        QMessageBox.critical(self, "Backend Error", error_message)

    def run_full_scrape(self):
        if not self.current_project: return
        config_path = self.export_project_config(save_to_temp=True)
        if not config_path: return
        self.status_bar.showMessage("🚀 Starting full scraping pipeline...")
        self.run_scrape_btn.setEnabled(False)

        if self.scrape_from_browser_checkbox.isChecked():
            self.browser.page().toHtml(lambda html: self._execute_backend_task(
                'run_scrape', config_path=config_path, html_content=html
            ))
        else:
            self._execute_backend_task('run_scrape', config_path=config_path)

    def on_scrape_finished(self, results: list, metrics: dict):
        self.run_scrape_btn.setEnabled(True)
        if self.backend_thread: self.backend_thread.quit()

        if not self.current_project: return
        base_output_dir = self.current_project.output_directory or "./data_exports"
        db_path = Path(base_output_dir) / f"{self.current_project.domain}_intelligence.db"

        try:
            inserter = DatabaseInserter(str(db_path))
            source_name = self.current_project.name.lower().replace(' ', '_')
            inserter.insert_player_stats(results, source_name)
            inserter.close()
            QMessageBox.information(self, "Scrape Complete",
                                    f"Scraping finished.\n{metrics.get('items_extracted', 0)} items processed.\nResults saved to database:\n{db_path}")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save results to the database: {e}")

    def export_project_config(self, save_to_temp=False) -> Optional[str]:
        if not self.current_project: return None
        config_data = self._create_backend_config_from_project(self.current_project)

        if save_to_temp:
            fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
            with os.fdopen(fd, 'w') as f:
                yaml.dump(config_data, f, indent=2)
            return path
        else:
            initial_dir = self.current_project.output_directory or "configs"
            Path(initial_dir).mkdir(parents=True, exist_ok=True)
            filename, _ = QFileDialog.getSaveFileName(self, "Export Config",
                                                      f"{initial_dir}/{self.current_project.name.lower().replace(' ', '_')}.yaml",
                                                      "YAML (*.yaml *.yml)")
            if not filename: return None
            with open(filename, 'w') as f:
                yaml.dump(config_data, f, indent=2)
            QMessageBox.information(self, "Export Complete", f"Config saved to:\n{filename}")
            return filename

    def _create_backend_config_from_project(self, project: ProjectConfig) -> Dict[str, Any]:
        def rule_to_dict(rule: ScrapingRule):
            d = {k: v for k, v in rule.to_dict().items() if v is not None}
            if "sub_selectors" in d and not d["sub_selectors"]: del d["sub_selectors"]
            return d

        source_name = project.name.lower().replace(' ', '_')
        base_output_dir = project.output_directory or f"./data_exports/{project.domain}"
        output_path = Path(base_output_dir) / f"{source_name}.jsonl"

        return {"domain_info": {"name": project.name, "description": project.description, "domain": project.domain},
                "sources": [{"name": source_name, "seeds": project.target_websites, "source_type": project.domain,
                             "selectors": {"custom_fields": [rule_to_dict(r) for r in project.scraping_rules]},
                             "crawl": project.rate_limiting,
                             "export": {"format": project.output_settings.get("format", "jsonl"),
                                        "output_path": str(output_path)}}]}