# rag_data_studio/components/project_panel.py
"""
UI components for managing projects: the list panel and the new/edit dialog.
NOW WITH PERSISTENCE! Projects are saved and loaded automatically.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from PySide6.QtWidgets import *
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

# Use the new centralized models
from ..core.models import ProjectConfig

class ProjectManager(QWidget):
    """Manages the list of projects, including loading and saving."""
    project_selected = Signal(ProjectConfig)
    new_project_requested = Signal()
    project_updated = Signal(ProjectConfig)

    def __init__(self):
        super().__init__()
        self.projects: Dict[str, ProjectConfig] = {}
        self.init_ui()
        self.load_projects_from_disk()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header = QLabel("📁 Projects")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet("color: #4CAF50; margin: 10px 0 5px 5px;")

        self.project_list_widget = QListWidget()
        self.project_list_widget.itemClicked.connect(self.on_project_list_item_selected)

        actions_layout = QHBoxLayout()
        self.new_btn = QPushButton("➕ New Project")
        self.edit_btn = QPushButton("✏️ Edit Project")
        self.delete_btn = QPushButton("🗑️ Delete Project")

        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        actions_layout.addWidget(self.new_btn)
        actions_layout.addWidget(self.edit_btn)
        actions_layout.addWidget(self.delete_btn)

        layout.addWidget(header)
        layout.addWidget(self.project_list_widget)
        layout.addLayout(actions_layout)

        self.new_btn.clicked.connect(self.handle_new_project_request)
        self.edit_btn.clicked.connect(self.edit_selected_project)
        self.delete_btn.clicked.connect(self.delete_selected_project)
        self.project_list_widget.currentItemChanged.connect(self.on_selection_changed)

    def on_selection_changed(self, current, previous):
        is_selected = current is not None
        self.edit_btn.setEnabled(is_selected)
        self.delete_btn.setEnabled(is_selected)

    def handle_new_project_request(self):
        self.new_project_requested.emit()

    def add_or_update_project(self, project: ProjectConfig):
        """Adds a new project or updates an existing one."""
        self.projects[project.id] = project
        self.save_projects_to_disk()
        self.refresh_project_list_display()
        # Find and select the new/updated item in the list
        for i in range(self.project_list_widget.count()):
            item = self.project_list_widget.item(i)
            if item.data(Qt.UserRole) == project.id:
                self.project_list_widget.setCurrentItem(item)
                self.on_project_list_item_selected(item)
                break
        self.project_updated.emit(project) # Emit signal that a project was updated

    def edit_selected_project(self):
        current_item = self.project_list_widget.currentItem()
        if not current_item:
            return
        project_id = current_item.data(Qt.UserRole)
        project_to_edit = self.projects.get(project_id)
        if project_to_edit:
            dialog = ProjectDialog(self, project_to_edit=project_to_edit)
            if dialog.exec() == QDialog.Accepted:
                updated_project = dialog.get_project_config()
                self.add_or_update_project(updated_project)


    def refresh_project_list_display(self):
        """Updates the visual list of projects."""
        current_id = None
        if self.project_list_widget.currentItem():
            current_id = self.project_list_widget.currentItem().data(Qt.UserRole)

        self.project_list_widget.clear()
        for project_id, project_obj in sorted(self.projects.items(), key=lambda item: item[1].name.lower()):
            item = QListWidgetItem(f" {project_obj.name}")
            item.setData(Qt.UserRole, project_id)
            item.setToolTip(f"Domain: {project_obj.domain}\nTargets: {len(project_obj.target_websites)}")
            self.project_list_widget.addItem(item)
            if project_id == current_id:
                self.project_list_widget.setCurrentItem(item)

    def on_project_list_item_selected(self, list_item: QListWidgetItem):
        if list_item:
            project_id = list_item.data(Qt.UserRole)
            project_obj = self.projects.get(project_id)
            if project_obj:
                self.project_selected.emit(project_obj)

    def get_project_path(self) -> Path:
        """Gets the path to the projects config file."""
        data_dir = Path.home() / ".rag_data_studio"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "projects.json"

    def save_projects_to_disk(self):
        """Saves all projects to a JSON file."""
        try:
            projects_data_to_save = {pid: p.to_dict() for pid, p in self.projects.items()}
            with open(self.get_project_path(), "w", encoding="utf-8") as f:
                json.dump(projects_data_to_save, f, indent=2)
            print(f"✅ Projects saved to {self.get_project_path()}")
        except Exception as e:
            print(f"❌ Error saving projects: {e}")

    def load_projects_from_disk(self):
        """Loads projects from the JSON file."""
        project_file = self.get_project_path()
        if not project_file.exists():
            print("No project file found. Starting fresh.")
            return

        try:
            with open(project_file, "r", encoding="utf-8") as f:
                projects_data_loaded = json.load(f)
            self.projects = {pid: ProjectConfig.from_dict(p_data) for pid, p_data in projects_data_loaded.items()}
            self.refresh_project_list_display()
            print(f"✅ Loaded {len(self.projects)} projects from {project_file}")
        except (json.JSONDecodeError, TypeError) as e:
            print(f"❌ Error loading or parsing projects file {project_file}: {e}. Creating a backup.")
            self.projects = {}
            try:
                import shutil
                shutil.copy(project_file, project_file.with_suffix('.json.bak'))
            except Exception as e_bak:
                print(f"Could not create backup of corrupted project file: {e_bak}")


    def delete_selected_project(self):
        current_item = self.project_list_widget.currentItem()
        if not current_item:
            return

        project_id = current_item.data(Qt.UserRole)
        project_name = self.projects[project_id].name
        reply = QMessageBox.question(self, "Delete Project", f"Are you sure you want to delete '{project_name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            del self.projects[project_id]
            self.save_projects_to_disk()
            self.refresh_project_list_display()
            QMessageBox.information(self, "Project Deleted", f"Project '{project_name}' has been deleted.")


class ProjectDialog(QDialog):
    """Dialog for creating a new project or editing an existing one."""
    def __init__(self, parent=None, project_to_edit: Optional[ProjectConfig] = None):
        super().__init__(parent)
        self.project_to_edit = project_to_edit
        self.setWindowTitle("Edit Project" if project_to_edit else "Create New Project")
        self.setModal(True)
        self.resize(550, 450)
        self.init_ui()
        if project_to_edit:
            self.populate_for_edit(project_to_edit)

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., ATP Tennis Stats Scraper")
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(70)
        self.description_input.setPlaceholderText("A brief description of the project's goal.")

        self.domain_combo = QComboBox()
        self.domain_combo.setEditable(True)
        self.domain_combo.addItems(["tennis_stats", "sports_general", "finance", "news", "ecommerce", "research", "custom"])

        # --- NEW UI ELEMENTS FOR OUTPUT DIRECTORY ---
        output_layout = QHBoxLayout()
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Default: (Project Folder)/data_exports/")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_for_directory)
        output_layout.addWidget(self.output_dir_input)
        output_layout.addWidget(browse_btn)

        self.websites_input = QTextEdit()
        self.websites_input.setPlaceholderText("Enter main target URLs, one per line (e.g., https://www.atptour.com/en/rankings/singles)")
        self.websites_input.setMaximumHeight(100)

        form_layout.addRow("Project Name*:", self.name_input)
        form_layout.addRow("Description:", self.description_input)
        form_layout.addRow("Primary Domain*:", self.domain_combo)
        form_layout.addRow("Output Directory:", output_layout) # Add the new layout here
        form_layout.addRow("Target Websites:", self.websites_input)

        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("💾 Save Project" if self.project_to_edit else "✨ Create Project")
        self.ok_btn.setProperty("class", "success")
        self.cancel_btn = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(form_layout)
        layout.addLayout(button_layout)

        self.ok_btn.clicked.connect(self.on_ok_clicked)
        self.cancel_btn.clicked.connect(self.reject)

    def browse_for_directory(self):
        """Opens a dialog to select an output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir_input.text() or str(Path.home()) # Start at home dir
        )
        if directory:
            self.output_dir_input.setText(directory)

    def populate_for_edit(self, project: ProjectConfig):
        self.name_input.setText(project.name)
        self.description_input.setPlainText(project.description)
        self.domain_combo.setCurrentText(project.domain)
        self.websites_input.setPlainText("\n".join(project.target_websites))
        if project.output_directory:
            self.output_dir_input.setText(project.output_directory)

    def on_ok_clicked(self):
        if not self.name_input.text().strip() or not self.domain_combo.currentText().strip():
            QMessageBox.warning(self, "Missing Information", "Project Name and Primary Domain are required.")
            return
        self.accept()

    def get_project_config(self) -> ProjectConfig:
        websites = [line.strip() for line in self.websites_input.toPlainText().split('\n') if line.strip()]
        output_dir = self.output_dir_input.text().strip() or None # Use None if empty

        if self.project_to_edit:
            self.project_to_edit.name = self.name_input.text().strip()
            self.project_to_edit.description = self.description_input.toPlainText().strip()
            self.project_to_edit.domain = self.domain_combo.currentText()
            self.project_to_edit.target_websites = websites
            self.project_to_edit.output_directory = output_dir
            self.project_to_edit.updated_at = datetime.now().isoformat()
            return self.project_to_edit
        else:
            return ProjectConfig(
                id=f"proj_{uuid.uuid4().hex[:10]}",
                name=self.name_input.text().strip(),
                description=self.description_input.toPlainText().strip(),
                domain=self.domain_combo.currentText(),
                target_websites=websites,
                output_directory=output_dir,
            )