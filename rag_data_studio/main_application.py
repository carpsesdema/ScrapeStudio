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
from .components.data_viewer import DataViewerDialog  # NEW
from .integration.backend_bridge import BackendWorker

# Import backend and storage components
from scraper.searcher import run_pipeline, run_pipeline_on_html
from storage.database_inserter import DatabaseInserter
from utils.logger import setup_logger


# Custom Exception for user cancellation
class UserCancelledError(Exception):
    pass


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
    QTabWidget::pane { border: 1px solid #404040; }
    QTabBar::tab { background: #404040; padding: 8px 16px; margin-right: 2px; }
    QTabBar::tab:selected { background: #4CAF50; }
    """


class ScrapeRunner(QObject):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str, int)

    def __init__(self, config_path: str, html_content: Optional[str] = None):
        super().__init__()
        self.config_path = config_path
        self.html_content = html_content
        self._is_interrupted = False
        self.results = []
        self.metrics = {}

    def run(self):
        """Execute the scraping pipeline with proper error handling."""
        try:
            print(f"🚀 ScrapeRunner starting...")
            print(f"   Config: {self.config_path}")
            print(f"   HTML mode: {self.html_content is not None}")

            def progress_callback(msg, percent):
                print(f"📊 {msg} ({percent}%)")
                if self._is_interrupted:
                    raise UserCancelledError("Scrape cancelled by user")
                self.progress.emit(msg, percent)

            # Import here to avoid circular imports
            if self.html_content:
                print("🌐 Processing browser HTML...")
                from scraper.searcher import run_pipeline_on_html
                self.results, self.metrics = run_pipeline_on_html(self.config_path, self.html_content,
                                                                  progress_callback)
            else:
                print("🌍 Processing URLs...")
                from scraper.searcher import run_pipeline
                self.results, self.metrics = run_pipeline(self.config_path, progress_callback)

            print(f"✅ Pipeline completed: {len(self.results)} items, {len(self.metrics.get('errors', []))} errors")

            if not self._is_interrupted:
                self.finished.emit("success")

        except UserCancelledError as e:
            print(f"❌ User cancelled: {e}")
            self.error.emit(str(e))
        except Exception as e:
            print(f"💥 Critical error: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"Critical error: {e}")

    def request_interruption(self):
        print("🛑 Interruption requested")
        self._is_interrupted = True


class RAGDataStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_project: Optional[ProjectConfig] = None
        self.backend_thread: Optional[QThread] = None
        self.test_thread: Optional[QThread] = None
        self.scrape_worker: Optional[ScrapeRunner] = None
        self.progress_dialog: Optional[QProgressDialog] = None
        self.logger = setup_logger()
        self.last_db_path: Optional[str] = None  # NEW: Track last database path
        self.init_ui()
        self.connect_signals()
        self.dark_mode_css_id = "scrape-studio-dark-mode"
        self.temp_config_path_for_scrape: Optional[str] = None

    def init_ui(self):
        self.setWindowTitle("RAG Data Studio - Professional Scraper Builder")
        self.setGeometry(100, 100, 1600, 1000)
        self.setStyleSheet(load_dark_theme())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Project Manager
        self.project_manager = ProjectManager()
        self.project_manager.setMinimumWidth(250)
        self.project_manager.setMaximumWidth(400)
        main_splitter.addWidget(self.project_manager)

        # Center panel - Browser
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
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

        # Right panel - Rules and Actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_splitter = QSplitter(Qt.Vertical)

        self.element_targeter = VisualElementTargeter()
        self.rules_manager = RulesManager()

        right_splitter.addWidget(self.element_targeter)
        right_splitter.addWidget(self.rules_manager)
        right_splitter.setSizes([450, 350])

        # Global actions
        global_actions_group = QGroupBox("Project Actions")
        global_actions_layout = QVBoxLayout(global_actions_group)

        self.scrape_from_browser_checkbox = QCheckBox("Scrape from current browser view")
        self.scrape_from_browser_checkbox.setToolTip("If checked, uses HTML currently visible in browser")

        # NEW: Two rows of buttons
        top_buttons_layout = QHBoxLayout()
        self.test_all_btn = QPushButton("🧪 Test All Rules")
        self.export_config_btn = QPushButton("💾 Export to YAML")
        self.run_scrape_btn = QPushButton("🚀 Run Full Scrape")
        self.run_scrape_btn.setProperty("class", "success")

        top_buttons_layout.addWidget(self.test_all_btn)
        top_buttons_layout.addWidget(self.export_config_btn)
        top_buttons_layout.addWidget(self.run_scrape_btn)

        # NEW: Bottom row with View Results button
        bottom_buttons_layout = QHBoxLayout()
        self.view_results_btn = QPushButton("👁️ View Results")
        self.view_results_btn.setEnabled(False)  # Disabled until we have results
        self.view_results_btn.setStyleSheet(
            "QPushButton { background-color: #9C27B0; } QPushButton:hover { background-color: #AB47BC; }")

        bottom_buttons_layout.addStretch()
        bottom_buttons_layout.addWidget(self.view_results_btn)
        bottom_buttons_layout.addStretch()

        global_actions_layout.addWidget(self.scrape_from_browser_checkbox)
        global_actions_layout.addLayout(top_buttons_layout)
        global_actions_layout.addLayout(bottom_buttons_layout)

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
        # Project management
        self.project_manager.project_selected.connect(self.load_project)
        self.project_manager.new_project_requested.connect(self.create_new_project)

        # Browser controls
        self.url_input.returnPressed.connect(self.load_page)
        self.load_btn.clicked.connect(self.load_page)
        self.selector_btn.toggled.connect(self.toggle_selector_mode)
        self.browser.element_selected.connect(self.element_targeter.update_selection)
        self.browser.loadFinished.connect(self.apply_dark_mode_on_load)
        self.dark_mode_checkbox.toggled.connect(self.toggle_dark_mode)

        # Rule management
        self.element_targeter.rule_created.connect(self.add_rule_to_project)
        self.element_targeter.batch_rules_created.connect(self.add_batch_rules_to_project)
        self.rules_manager.delete_rule_requested.connect(self.delete_rule_from_project)
        self.rules_manager.add_sub_rule_requested.connect(self.set_targeter_for_sub_rule)

        # Actions
        self.test_all_btn.clicked.connect(self.test_all_rules)
        self.export_config_btn.clicked.connect(self.export_project_config)
        self.run_scrape_btn.clicked.connect(self.run_full_scrape)
        self.view_results_btn.clicked.connect(self.view_results)  # NEW

    def apply_dark_mode_on_load(self, ok):
        if ok and self.dark_mode_checkbox.isChecked():
            self.toggle_dark_mode(True)

    def toggle_dark_mode(self, checked):
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
        dialog = ProjectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            new_project = dialog.get_project_config()
            self.project_manager.add_or_update_project(new_project)
            self.load_project(new_project)

    def load_project(self, project: ProjectConfig):
        self.current_project = project
        self.rules_manager.set_rules(project.scraping_rules)
        self.element_targeter.reset_mode()
        if project.target_websites:
            self.url_input.setText(project.target_websites[0])
        self.status_bar.showMessage(f"Loaded project: {project.name}")

        # Check if results exist for this project
        self._check_for_existing_results()

    def _check_for_existing_results(self):
        """Check if database results exist for the current project."""
        if not self.current_project:
            self.view_results_btn.setEnabled(False)
            return

        base_output_dir = self.current_project.output_directory or "./data_exports"
        sanitized_project_name = self.current_project.name.lower().replace(' ', '_')
        db_path = Path(base_output_dir) / f"{sanitized_project_name}.db"

        if db_path.exists():
            self.last_db_path = str(db_path)
            self.view_results_btn.setEnabled(True)
            self.view_results_btn.setText(f"👁️ View Results ({db_path.name})")
        else:
            self.view_results_btn.setEnabled(False)
            self.view_results_btn.setText("👁️ View Results")

    def save_current_project(self):
        if self.current_project:
            self.current_project.updated_at = QDateTime.currentDateTime().toString(Qt.ISODate)
            self.project_manager.add_or_update_project(self.current_project)
            self.status_bar.showMessage(f"Project '{self.current_project.name}' saved.", 3000)

    def add_rule_to_project(self, rule: ScrapingRule, parent_id: Optional[str]):
        if not self.current_project:
            return

        if parent_id:
            parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_id)
            if parent_rule:
                parent_rule.sub_selectors.append(rule)
        else:
            self.current_project.scraping_rules.append(rule)

        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()

    def add_batch_rules_to_project(self, rules: List[ScrapingRule]):
        if not self.current_project:
            return
        self.current_project.scraping_rules.extend(rules)
        self.rules_manager.set_rules(self.current_project.scraping_rules)
        self.save_current_project()

    def delete_rule_from_project(self, rule_id: str):
        if not self.current_project:
            return

        reply = QMessageBox.question(self, "Delete Rule", "Delete this rule?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return

        def find_and_remove(rules: List[ScrapingRule], r_id: str) -> bool:
            for i, r in enumerate(rules):
                if r.id == r_id:
                    del rules[i]
                    return True
                if find_and_remove(r.sub_selectors, r_id):
                    return True
            return False

        if find_and_remove(self.current_project.scraping_rules, rule_id):
            self.rules_manager.set_rules(self.current_project.scraping_rules)
            self.save_current_project()

    def set_targeter_for_sub_rule(self, parent_rule_id: str):
        if not self.current_project:
            return
        parent_rule = self._find_rule_by_id(self.current_project.scraping_rules, parent_rule_id)
        if parent_rule:
            self.element_targeter.set_mode_for_sub_field(parent_rule)

    def _find_rule_by_id(self, rules: List[ScrapingRule], r_id: str) -> Optional[ScrapingRule]:
        for rule in rules:
            if rule.id == r_id:
                return rule
            found = self._find_rule_by_id(rule.sub_selectors, r_id)
            if found:
                return found
        return None

    def load_page(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.browser.load(QUrl(url))

    def toggle_selector_mode(self, checked):
        if checked:
            self.browser.enable_selector_mode()
        else:
            self.browser.disable_selector_mode()
        self.selector_btn.setText("❌ Stop Targeting" if checked else "🎯 Target Elements")
        if not checked:
            self.element_targeter.reset_mode()

    def test_all_rules(self):
        if not self.current_project or not self.browser.url().isValid():
            QMessageBox.warning(self, "Cannot Test", "Please load a project and navigate to a URL first.")
            return

        url = self.browser.url().toString()
        rules = [r.to_dict() for r in self.current_project.scraping_rules]

        self._cleanup_test_thread()

        self.test_thread = QThread()
        worker = BackendWorker(self.logger)
        worker.moveToThread(self.test_thread)

        worker.test_results_ready.connect(self.on_test_results_ready)
        worker.error_occurred.connect(self.on_test_error)

        self.test_thread.started.connect(lambda: worker.test_selectors_on_url(url, rules))
        self.test_thread.finished.connect(self._cleanup_test_thread)
        self.test_thread.start()

    def on_test_results_ready(self, results: dict):
        dialog = TestResultsDialog(results, self, test_url=self.browser.url().toString())
        dialog.exec()

    def on_test_error(self, error_message: str):
        QMessageBox.critical(self, "Test Error", error_message)

    def _cleanup_test_thread(self):
        """Clean up the test thread safely."""
        if self.test_thread:
            if self.test_thread.isRunning():
                self.test_thread.quit()
                self.test_thread.wait(3000)
            self.test_thread.deleteLater()
            self.test_thread = None

    def on_backend_error(self, error_message: str):
        self._cleanup_scrape_resources()
        if "cancelled by user" in error_message.lower():
            self.status_bar.showMessage("Operation cancelled.", 4000)
        else:
            QMessageBox.critical(self, "Error", error_message)

    def _is_scrape_running(self) -> bool:
        """Safely check if a scrape is running."""
        try:
            return (self.backend_thread is not None and
                    self.backend_thread.isRunning())
        except RuntimeError:
            self.backend_thread = None
            return False

    def run_full_scrape(self):
        """Execute the full scraping pipeline."""
        if self._is_scrape_running():
            QMessageBox.warning(self, "Scrape in Progress", "A scrape is already running. Please wait.")
            return

        if not self.current_project:
            QMessageBox.warning(self, "No Project", "Please create and load a project first.")
            return

        if not self.current_project.scraping_rules:
            QMessageBox.warning(self, "No Rules", "Please define some scraping rules first.")
            return

        self._cleanup_scrape_resources()

        self.temp_config_path_for_scrape = self.export_project_config(save_to_temp=True)
        if not self.temp_config_path_for_scrape:
            QMessageBox.critical(self, "Config Error", "Failed to generate scraping configuration.")
            return

        self.progress_dialog = QProgressDialog("Initializing scrape...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Scraping in Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._cancel_scrape)

        self.run_scrape_btn.setEnabled(False)
        self.run_scrape_btn.setText("⏳ Scraping...")

        self.progress_dialog.show()
        QApplication.processEvents()

        if self.scrape_from_browser_checkbox.isChecked():
            print("🌐 Getting HTML from browser...")
            self.browser.page().toHtml(self._initiate_scrape_with_html)
        else:
            print("🌍 Running URL-based scrape...")
            self._initiate_scrape_with_html(None)

    def _initiate_scrape_with_html(self, html_content: Optional[str]):
        """Start the actual scraping process."""
        if not self.temp_config_path_for_scrape:
            self._cleanup_scrape_resources()
            return

        print(f"🚀 Initiating scrape with config: {self.temp_config_path_for_scrape}")

        self.backend_thread = QThread()
        self.scrape_worker = ScrapeRunner(self.temp_config_path_for_scrape, html_content)
        self.scrape_worker.moveToThread(self.backend_thread)

        self.scrape_worker.progress.connect(self._update_progress)
        self.scrape_worker.finished.connect(self._on_scrape_finished)
        self.scrape_worker.error.connect(self.on_backend_error)

        self.backend_thread.started.connect(self.scrape_worker.run)
        self.backend_thread.finished.connect(self._on_thread_finished)

        print("🎯 Starting scrape worker thread...")
        self.backend_thread.start()

    def _update_progress(self, message: str, percentage: int):
        """Update the progress dialog."""
        if self.progress_dialog and not self.progress_dialog.wasCanceled():
            self.progress_dialog.setLabelText(message)
            self.progress_dialog.setValue(percentage)
            QApplication.processEvents()

    def _cancel_scrape(self):
        """Cancel the running scrape operation."""
        print("🛑 User requested scrape cancellation")
        if self.scrape_worker:
            self.scrape_worker.request_interruption()
        if self.backend_thread:
            self.backend_thread.requestInterruption()

    def _on_scrape_finished(self, status: str):
        """Handle successful scrape completion."""
        print(f"✅ Scrape finished with status: {status}")

        if self.scrape_worker and status == "success":
            results = self.scrape_worker.results
            metrics = self.scrape_worker.metrics

            print(f"📊 Final results: {len(results)} items extracted")

            if not self.current_project:
                self._cleanup_scrape_resources()
                return

            try:
                base_output_dir = self.current_project.output_directory or "./data_exports"
                Path(base_output_dir).mkdir(parents=True, exist_ok=True)

                sanitized_project_name = self.current_project.name.lower().replace(' ', '_')
                db_path = Path(base_output_dir) / f"{sanitized_project_name}.db"

                print(f"💾 Saving to database: {db_path}")
                inserter = DatabaseInserter(str(db_path))
                inserter.insert_player_stats(results)
                inserter.close()

                # Store the database path for viewing results
                self.last_db_path = str(db_path)
                self.view_results_btn.setEnabled(True)
                self.view_results_btn.setText(f"👁️ View Results ({db_path.name})")

                success_msg = f"""✅ Scraping Complete!

📊 Results:
- {len(results)} items extracted
- {metrics.get('urls_fetched', 0)} URLs processed
- {len(metrics.get('errors', []))} errors

💾 Data saved to:
{db_path}

🎯 Ready for RAG ingestion!

Click "View Results" to see your data!"""

                self._cleanup_scrape_resources()
                QMessageBox.information(self, "Scrape Complete", success_msg)
                self.status_bar.showMessage(f"✅ Scraped {len(results)} items successfully", 10000)

            except Exception as e:
                print(f"❌ Database save error: {e}")
                self._cleanup_scrape_resources()
                QMessageBox.critical(self, "Database Error", f"Scraping succeeded but database save failed:\n{e}")
        else:
            self._cleanup_scrape_resources()

    def _on_thread_finished(self):
        """Handle thread finished signal."""
        print("🔧 Backend thread finished")

    def _cleanup_scrape_resources(self):
        """Clean up all scraping-related resources."""
        print("🧹 Cleaning up scrape resources...")

        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        self.run_scrape_btn.setEnabled(True)
        self.run_scrape_btn.setText("🚀 Run Full Scrape")

        if self.temp_config_path_for_scrape and os.path.exists(self.temp_config_path_for_scrape):
            try:
                os.unlink(self.temp_config_path_for_scrape)
            except:
                pass
            self.temp_config_path_for_scrape = None

        if self.scrape_worker:
            self.scrape_worker.deleteLater()
            self.scrape_worker = None

        if self.backend_thread:
            try:
                if self.backend_thread.isRunning():
                    self.backend_thread.quit()
                    self.backend_thread.wait(3000)
                self.backend_thread.deleteLater()
            except RuntimeError:
                pass
            self.backend_thread = None

    def view_results(self):
        """Open the data viewer dialog."""
        if not self.last_db_path or not Path(self.last_db_path).exists():
            QMessageBox.warning(self, "No Results", "No database results found. Run a scrape first!")
            return

        try:
            dialog = DataViewerDialog(self.last_db_path, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Viewer Error", f"Failed to open data viewer:\n{e}")

    def closeEvent(self, event):
        """Handle application close event."""
        print("🔒 Application closing, cleaning up resources...")

        self._cleanup_scrape_resources()
        self._cleanup_test_thread()

        event.accept()

    def export_project_config(self, save_to_temp=False) -> Optional[str]:
        """Export project configuration to YAML."""
        if not self.current_project:
            return None

        try:
            config_data = self._create_backend_config_from_project(self.current_project)

            if save_to_temp:
                fd, path = tempfile.mkstemp(suffix=".yaml", text=True)
                with os.fdopen(fd, 'w') as f:
                    yaml.dump(config_data, f, indent=2)
                print(f"📄 Temp config saved to: {path}")
                return path
            else:
                initial_dir = self.current_project.output_directory or "configs"
                Path(initial_dir).mkdir(parents=True, exist_ok=True)
                filename, _ = QFileDialog.getSaveFileName(
                    self, "Export Config",
                    f"{initial_dir}/{self.current_project.name.lower().replace(' ', '_')}.yaml",
                    "YAML (*.yaml *.yml)"
                )
                if not filename:
                    return None

                with open(filename, 'w') as f:
                    yaml.dump(config_data, f, indent=2)
                QMessageBox.information(self, "Export Complete", f"Config saved to:\n{filename}")
                return filename

        except Exception as e:
            print(f"❌ Config export failed: {e}")
            if not save_to_temp:
                QMessageBox.critical(self, "Export Failed", f"Failed to export configuration:\n{e}")
            return None

    def _create_backend_config_from_project(self, project: ProjectConfig) -> Dict[str, Any]:
        """Create backend configuration from project."""

        def rule_to_dict(rule: ScrapingRule):
            d = rule.to_dict()
            return d

        source_name = project.name.lower().replace(' ', '_')
        base_output_dir = project.output_directory or f"./data_exports/{project.domain}"
        output_path = Path(base_output_dir) / f"{source_name}.jsonl"

        target_urls = project.target_websites if project.target_websites else ["https://example.com"]

        return {
            "domain_info": {
                "name": project.name,
                "description": project.description,
                "domain": project.domain
            },
            "sources": [{
                "name": source_name,
                "seeds": target_urls,
                "source_type": project.domain,
                "selectors": {
                    "custom_fields": [rule_to_dict(r) for r in project.scraping_rules]
                },
                "crawl": project.rate_limiting,
                "export": {
                    "format": project.output_settings.get("format", "jsonl"),
                    "output_path": str(output_path)
                }
            }]
        }