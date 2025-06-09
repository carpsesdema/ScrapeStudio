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


# Custom Exception for user cancellation
class UserCancelledError(Exception):
    pass


# It's good practice to have the theme as a separate function or in a separate file
def load_dark_theme():
    # Theme CSS remains the same...
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
    QProgressDialog {
        background-color: #2d2d2d;
    }
    QProgressBar {
        text-align: center;
        background-color: #3a3a3a;
        border: 1px solid #555;
        border-radius: 5px;
    }
    QProgressBar::chunk {
        background-color: #4CAF50;
        border-radius: 4px;
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
    finished = Signal(list, dict)
    error = Signal(str)
    progress = Signal(str, int)

    def __init__(self, config_path: str, html_content: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.html_content = html_content
        self._is_interrupted = False

    def run(self):
        try:
            def progress_callback(msg, percent):
                if self._is_interrupted:
                    raise UserCancelledError("Scrape job cancelled by user.")
                self.progress.emit(msg, percent)

            if self.html_content:
                results, metrics = run_pipeline_on_html(self.config_path, self.html_content, progress_callback)
            else:
                results, metrics = run_pipeline(self.config_path, progress_callback)

            if not self._is_interrupted:
                self.finished.emit(results, metrics)

        except UserCancelledError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))

    def request_interruption(self):
        self._is_interrupted = True


class RAGDataStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_project: Optional[ProjectConfig] = None
        self.backend_thread: Optional[QThread] = None
        self.progress_dialog: Optional[QProgressDialog] = None
        self.logger = setup_logger()
        self.init_ui()
        self.connect_signals()
        self.dark_mode_css_id = "scrape-studio-dark-mode"
        self.temp_config_path_for_scrape: Optional[str] = None

    def init_ui(self):
        # UI Initialization is correct, no changes needed here.
        # ... (omitting for brevity)
        self.setWindowTitle("Scrape Studio - Visual Scraper Builder")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet(load_dark_theme())
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_splitter = QSplitter(Qt.Horizontal)
        self.project_manager = ProjectManager()
        self.project_manager.setMinimumWidth(250)
        self.project_manager.setMaximumWidth(400)
        main_splitter.addWidget(self.project_manager)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL to analyze and press Enter...")
        self.load_btn = QPushButton("🌐 Load")
        self.dark_mode_checkbox = QCheckBox("Dark Mode")
        self.dark_mode_checkbox.setChecked(True)
        self.selector_btn = QPushButton("🎯 Target Elements")
        self.selector_btn.setProperty("class", "success")
        self.selector_btn.setCheckable(True)
        toolbar_layout.addWidget(self.url_input)
        toolbar_layout.addWidget(self.load_btn)
        toolbar_layout.addWidget(self.dark_mode_checkbox)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.selector_btn)
        self.browser = InteractiveBrowser()
        center_layout.addLayout(toolbar_layout)
        center_layout.addWidget(self.browser)
        main_splitter.addWidget(center_widget)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_splitter = QSplitter(Qt.Vertical)
        self.element_targeter = VisualElementTargeter()
        self.rules_manager = RulesManager()
        right_splitter.addWidget(self.element_targeter)
        right_splitter.addWidget(self.rules_manager)
        right_splitter.setSizes([450, 350])
        global_actions_group = QGroupBox("Project Actions")
        global_actions_layout = QVBoxLayout(global_actions_group)
        self.scrape_from_browser_checkbox = QCheckBox("Scrape from current browser view")
        self.scrape_from_browser_checkbox.setToolTip(
            "If checked, the scraper uses the HTML currently visible in the browser.")
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
        # ... (all other connections remain the same)
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
        self.test_all_btn.clicked.connect(self.test_all_rules)
        self.export_config_btn.clicked.connect(self.export_project_config)
        self.run_scrape_btn.clicked.connect(self.run_full_scrape)
        self.browser.loadFinished.connect(self.apply_dark_mode_on_load)
        self.dark_mode_checkbox.toggled.connect(self.toggle_dark_mode)

    # --- Methods ---
    def apply_dark_mode_on_load(self, ok):
        if ok and self.dark_mode_checkbox.isChecked(): self.toggle_dark_mode(True)

    def toggle_dark_mode(self, checked):
        # ... (code from previous step, no changes)
        dark_mode_css = f"""
        const id = '{self.dark_mode_css_id}';
        let style = document.getElementById(id);
        if ({str(checked).lower()}) {{
            if (!style) {{
                style = document.createElement('style');
                style.id = id;
                document.head.appendChild(style);
            }}
            style.innerHTML = `
                html, body, img, picture, video {{
                    background-color: #121212 !important;
                    filter: invert(1) hue-rotate(180deg) !important;
                }}
                img, picture, video {{
                    filter: invert(1) hue-rotate(180deg) !important;
                }}
                html, body {{
                   color-scheme: dark !important;
                }}
            `;
        }} else {{
            if (style) {{
                style.remove();
            }}
        }}
        """
        self.browser.page().runJavaScript(dark_mode_css)

    def create_new_project(self):
        # ... (code from previous step, no changes)
        dialog = ProjectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_project = dialog.get_project_config()
            self.project_manager.add_or_update_project(new_project)
            self.load_project(new_project)

    def load_project(self, project: ProjectConfig):
        # ... (code from previous step, no changes)
        self.current_project = project;
        self.rules_manager.set_rules(project.scraping_rules)
        self.element_targeter.reset_mode()
        if project.target_websites: self.url_input.setText(project.target_websites[0])
        self.status_bar.showMessage(f"Loaded project: {project.name}")

    def save_current_project(self):
        # ... (code from previous step, no changes)
        if self.current_project:
            self.current_project.updated_at = QDateTime.currentDateTime().toString(Qt.ISODate)
            self.project_manager.add_or_update_project(self.current_project)
            self.status_bar.showMessage(f"Project '{self.current_project.name}' saved.", 3000)

    def add_rule_to_project(self, rule: ScrapingRule, parent_id: Optional[str]):
        # ... (code from previous step, no changes)
        if not self.current_project: return
        if parent_id:
            parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_id)
            if parent_rule: parent_rule.sub_selectors.append(rule)
        else:
            self.current_project.scraping_rules.append(rule)
        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()

    def add_batch_rules_to_project(self, rules: List[ScrapingRule]):
        # ... (code from previous step, no changes)
        if not self.current_project: return
        self.current_project.scraping_rules.extend(rules)
        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()

    def delete_rule_from_project(self, rule_id: str):
        # ... (code from previous step, no changes)
        if not self.current_project: return
        reply = QMessageBox.question(self, "Delete Rule", "Delete this rule?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return

        def find_and_remove(rules: List[ScrapingRule], r_id: str) -> bool:
            for i, r in enumerate(rules):
                if r.id == r_id: del rules[i]; return True
                if find_and_remove(r.sub_selectors, r_id): return True
            return False

        if find_and_remove(self.current_project.scraping_rules, rule_id):
            self.rules_manager.set_rules(self.current_project.scraping_rules)
            self.save_current_project()

    def set_targeter_for_sub_rule(self, parent_rule_id: str):
        # ... (code from previous step, no changes)
        if not self.current_project: return
        parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_rule_id)
        if parent_rule: self.element_targeter.set_mode_for_sub_field(parent_rule)

    def _find_rule_by_id(self, rules: List[ScrapingRule], r_id: str) -> Optional[ScrapingRule]:
        # ... (code from previous step, no changes)
        for rule in rules:
            if rule.id == r_id: return rule
            found = self._find_rule_by_id(rule.sub_selectors, r_id)
            if found: return found
        return None

    def load_page(self):
        # ... (code from previous step, no changes)
        url = self.url_input.text().strip()
        if not url: return
        if not url.startswith(('http://', 'https://')): url = 'https://' + url
        self.browser.load(QUrl(url))

    def toggle_selector_mode(self, checked):
        # ... (code from previous step, no changes)
        if checked:
            self.browser.enable_selector_mode()
        else:
            self.browser.disable_selector_mode()
        self.selector_btn.setText("❌ Stop Targeting" if checked else "🎯 Target Elements")
        if not checked: self.element_targeter.reset_mode()

    def test_all_rules(self):
        # ... (code from previous step, no changes)
        if not self.current_project or not self.browser.url().isValid(): return
        url = self.browser.url().toString()
        rules = [r.to_dict() for r in self.current_project.scraping_rules]
        self.backend_thread = QThread()
        worker = BackendWorker(self.logger)
        worker.moveToThread(self.backend_thread)
        worker.test_results_ready.connect(self.on_test_results_ready)
        worker.error_occurred.connect(self.on_backend_error)
        self.backend_thread.started.connect(lambda: worker.test_selectors_on_url(url, rules))
        self.backend_thread.finished.connect(self.backend_thread.deleteLater)
        self.backend_thread.start()

    def on_test_results_ready(self, results: dict):
        if self.backend_thread: self.backend_thread.quit()
        dialog = TestResultsDialog(results, self, test_url=self.browser.url().toString())
        dialog.exec()

    def on_backend_error(self, error_message: str):
        self.run_scrape_btn.setEnabled(True)
        if self.progress_dialog: self.progress_dialog.close()
        if self.backend_thread: self.backend_thread.quit()
        if "cancelled by user" in error_message:
            self.status_bar.showMessage("Scrape cancelled.", 4000)
        else:
            QMessageBox.critical(self, "Backend Error", error_message)

    def run_full_scrape(self):
        if self.backend_thread and self.backend_thread.isRunning(): return
        if not self.current_project: return

        self.temp_config_path_for_scrape = self.export_project_config(save_to_temp=True)
        if not self.temp_config_path_for_scrape: return

        self.progress_dialog = QProgressDialog("Starting scrape...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Pipeline Running")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.show()

        self.run_scrape_btn.setEnabled(False)

        if self.scrape_from_browser_checkbox.isChecked():
            self.browser.page().toHtml(self._initiate_scrape_with_html)
        else:
            self._initiate_scrape_with_html(None)

    def _initiate_scrape_with_html(self, html_content: Optional[str]):
        config_path = self.temp_config_path_for_scrape
        if not config_path: return

        self.backend_thread = QThread()
        worker = ScrapeRunner(config_path, html_content)
        worker.moveToThread(self.backend_thread)
        worker.progress.connect(self.update_progress)
        worker.finished.connect(self.on_scrape_finished)
        worker.error.connect(self.on_backend_error)
        self.progress_dialog.canceled.connect(worker.request_interruption)
        self.backend_thread.started.connect(worker.run)
        self.backend_thread.finished.connect(worker.deleteLater)
        self.backend_thread.finished.connect(self.backend_thread.deleteLater)
        self.backend_thread.start()

    def update_progress(self, message: str, percentage: int):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            self.progress_dialog.setValue(percentage)
            if self.progress_dialog.wasCanceled(): self.backend_thread.requestInterruption()

    def on_scrape_finished(self, results: list, metrics: dict):
        if self.progress_dialog: self.progress_dialog.close()
        self.run_scrape_btn.setEnabled(True)
        if self.backend_thread: self.backend_thread.quit()

        if not self.current_project: return

        # --- THIS IS THE FIX ---
        # Use the project name to create the database file name
        base_output_dir = self.current_project.output_directory or "./data_exports"
        sanitized_project_name = self.current_project.name.lower().replace(' ', '_')
        db_path = Path(base_output_dir) / f"{sanitized_project_name}.db"

        try:
            inserter = DatabaseInserter(str(db_path))
            inserter.insert_player_stats(results)
            inserter.close()
            QMessageBox.information(self, "Scrape Complete",
                                    f"Scraping finished.\n{metrics.get('items_extracted', 0)} items processed.\nResults saved to database:\n{db_path}")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save results to the database: {e}")

    def export_project_config(self, save_to_temp=False) -> Optional[str]:
        # ... no changes ...
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
        # ... no changes ...
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