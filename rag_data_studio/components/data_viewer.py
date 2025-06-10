# rag_data_studio/components/data_viewer.py
"""
Data viewer dialog for showing scraped results in a beautiful format.
"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class DataViewerDialog(QDialog):
    """Dialog to view scraped data results in a nice format."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("📊 Scraped Data Results")
        self.setModal(True)
        self.resize(1200, 800)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("📊 Scraped Data Results")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #4CAF50; margin: 10px 0; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Database info
        self.info_label = QLabel()
        self.info_label.setStyleSheet("background: #2d2d2d; padding: 10px; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(self.info_label)

        # Tab widget for different views
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Summary tab
        self.summary_widget = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_widget)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 10))
        self.summary_layout.addWidget(self.summary_text)
        self.tab_widget.addTab(self.summary_widget, "📈 Summary")

        # Players table tab
        self.players_table = QTableWidget()
        self.tab_widget.addTab(self.players_table, "👥 Players")

        # Statistics table tab
        self.stats_table = QTableWidget()
        self.tab_widget.addTab(self.stats_table, "📊 Statistics")

        # Raw data tab
        self.raw_widget = QWidget()
        self.raw_layout = QVBoxLayout(self.raw_widget)
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        self.raw_text.setFont(QFont("Consolas", 9))
        self.raw_layout.addWidget(self.raw_text)
        self.tab_widget.addTab(self.raw_widget, "🔍 Raw Data")

        # Buttons
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton("💾 Export to CSV")
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.close_btn = QPushButton("Close")

        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        # Connect signals
        self.export_btn.clicked.connect(self.export_to_csv)
        self.refresh_btn.clicked.connect(self.load_data)
        self.close_btn.clicked.connect(self.accept)

    def load_data(self):
        """Load and display data from the SQLite database."""
        if not Path(self.db_path).exists():
            self.info_label.setText(f"❌ Database not found: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get database info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            db_size = Path(self.db_path).stat().st_size / 1024  # KB
            self.info_label.setText(
                f"📁 Database: {Path(self.db_path).name} | Size: {db_size:.1f} KB | Tables: {', '.join(tables)}")

            # Load summary
            self.load_summary(cursor)

            # Load tables
            if 'players' in tables:
                self.load_players_table(cursor)
            if 'player_statistics' in tables:
                self.load_stats_table(cursor)

            # Load raw data sample
            self.load_raw_data(cursor)

            conn.close()

        except Exception as e:
            self.info_label.setText(f"❌ Error loading data: {e}")

    def load_summary(self, cursor):
        """Load summary statistics."""
        summary_text = "📊 DATA EXTRACTION SUMMARY\n"
        summary_text += "=" * 50 + "\n\n"

        try:
            # Players count
            cursor.execute("SELECT COUNT(*) FROM players")
            player_count = cursor.fetchone()[0]

            # Stats count
            cursor.execute("SELECT COUNT(*) FROM player_statistics")
            stats_count = cursor.fetchone()[0]

            summary_text += f"👥 Total Players: {player_count:,}\n"
            summary_text += f"📊 Total Statistics Records: {stats_count:,}\n\n"

            # Sample player names
            cursor.execute("SELECT name FROM players LIMIT 10")
            sample_players = [row[0] for row in cursor.fetchall()]
            summary_text += f"👤 Sample Players:\n"
            for player in sample_players:
                summary_text += f"   • {player}\n"

            # Data completeness
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN first_serve_percentage IS NOT NULL THEN 1 END) as serve_pct_filled,
                    COUNT(*) as total
                FROM player_statistics
            """)
            result = cursor.fetchone()
            if result and result[1] > 0:
                completeness = (result[0] / result[1]) * 100
                summary_text += f"\n📈 Data Completeness (First Serve %): {completeness:.1f}%\n"

            summary_text += f"\n✅ Data extraction completed successfully!"
            summary_text += f"\n🎯 Ready for RAG pipeline ingestion!"

        except Exception as e:
            summary_text += f"❌ Error generating summary: {e}"

        self.summary_text.setPlainText(summary_text)

    def load_players_table(self, cursor):
        """Load players data into table widget."""
        try:
            cursor.execute("SELECT * FROM players LIMIT 100")
            players = cursor.fetchall()

            if not players:
                return

            # Get column names
            cursor.execute("PRAGMA table_info(players)")
            columns = [col[1] for col in cursor.fetchall()]

            self.players_table.setRowCount(len(players))
            self.players_table.setColumnCount(len(columns))
            self.players_table.setHorizontalHeaderLabels(columns)

            for row, player in enumerate(players):
                for col, value in enumerate(player):
                    item = QTableWidgetItem(str(value) if value else "")
                    self.players_table.setItem(row, col, item)

            self.players_table.resizeColumnsToContents()

        except Exception as e:
            print(f"Error loading players table: {e}")

    def load_stats_table(self, cursor):
        """Load statistics data into table widget."""
        try:
            cursor.execute("SELECT * FROM player_statistics LIMIT 100")
            stats = cursor.fetchall()

            if not stats:
                return

            # Get column names
            cursor.execute("PRAGMA table_info(player_statistics)")
            columns = [col[1] for col in cursor.fetchall()]

            self.stats_table.setRowCount(len(stats))
            self.stats_table.setColumnCount(len(columns))
            self.stats_table.setHorizontalHeaderLabels(columns)

            for row, stat in enumerate(stats):
                for col, value in enumerate(stat):
                    item = QTableWidgetItem(str(value) if value else "")
                    self.stats_table.setItem(row, col, item)

            self.stats_table.resizeColumnsToContents()

        except Exception as e:
            print(f"Error loading stats table: {e}")

    def load_raw_data(self, cursor):
        """Load raw data sample."""
        try:
            raw_text = "🔍 RAW DATA SAMPLE\n"
            raw_text += "=" * 50 + "\n\n"

            # Show first 5 statistics records with player names
            cursor.execute("""
                SELECT p.name, ps.* 
                FROM player_statistics ps 
                JOIN players p ON ps.player_id = p.id 
                LIMIT 5
            """)

            records = cursor.fetchall()

            if records:
                cursor.execute("PRAGMA table_info(player_statistics)")
                stat_columns = ['player_name'] + [col[1] for col in cursor.fetchall()]

                for i, record in enumerate(records, 1):
                    raw_text += f"📋 Record {i}:\n"
                    for col_name, value in zip(stat_columns, record):
                        if value:  # Only show non-empty values
                            raw_text += f"   {col_name}: {value}\n"
                    raw_text += "\n"
            else:
                raw_text += "No data found in database.\n"

        except Exception as e:
            raw_text = f"❌ Error loading raw data: {e}"

        self.raw_text.setPlainText(raw_text)

    def export_to_csv(self):
        """Export data to CSV files."""
        try:
            output_dir = Path(self.db_path).parent / "csv_exports"
            output_dir.mkdir(exist_ok=True)

            conn = sqlite3.connect(self.db_path)

            # Export players
            import pandas as pd
            players_df = pd.read_sql_query("SELECT * FROM players", conn)
            players_csv = output_dir / "players.csv"
            players_df.to_csv(players_csv, index=False)

            # Export statistics
            stats_df = pd.read_sql_query("""
                SELECT p.name as player_name, ps.* 
                FROM player_statistics ps 
                JOIN players p ON ps.player_id = p.id
            """, conn)
            stats_csv = output_dir / "player_statistics.csv"
            stats_df.to_csv(stats_csv, index=False)

            conn.close()

            QMessageBox.information(self, "Export Complete",
                                    f"Data exported to:\n{output_dir}\n\nFiles:\n• players.csv\n• player_statistics.csv")

        except ImportError:
            QMessageBox.warning(self, "Export Error",
                                "pandas is required for CSV export.\nInstall with: pip install pandas")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{e}")