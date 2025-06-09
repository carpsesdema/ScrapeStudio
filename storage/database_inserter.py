# storage/database_inserter.py
"""
Handles saving structured data into the SQLite Tennis Intelligence Database.
"""
import sqlite3
import logging
from typing import List, Dict, Any
from pathlib import Path

# Use the structured data model from the scraper
from scraper.rag_models import StructuredDataItem

logger = logging.getLogger(__name__)

DB_SCHEMA = """
-- Paste your entire schema here
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_player_id VARCHAR(50) UNIQUE,
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100),
    gender VARCHAR(10),
    country_code VARCHAR(3),
    country_name VARCHAR(100),
    date_of_birth DATE,
    turned_pro INTEGER,
    height_cm INTEGER,
    weight_kg INTEGER,
    plays VARCHAR(20),
    backhand VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    ranking_date DATE,
    atp_ranking INTEGER,
    wta_ranking INTEGER,
    ranking_points INTEGER,
    ranking_movement INTEGER,
    weeks_at_ranking INTEGER,
    previous_ranking INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(player_id, ranking_date)
);

CREATE TABLE IF NOT EXISTS player_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    stat_date DATE,
    surface VARCHAR(20),
    timeframe VARCHAR(20),
    matches_played INTEGER DEFAULT 0,
    matches_won INTEGER DEFAULT 0,
    matches_lost INTEGER DEFAULT 0,
    win_percentage DECIMAL(5,2),
    sets_won INTEGER DEFAULT 0,
    sets_lost INTEGER DEFAULT 0,
    straight_sets_wins INTEGER DEFAULT 0,
    three_set_wins INTEGER DEFAULT 0,
    five_set_wins INTEGER DEFAULT 0,
    aces_per_match DECIMAL(4,2),
    double_faults_per_match DECIMAL(4,2),
    first_serve_percentage DECIMAL(5,2),
    first_serve_points_won DECIMAL(5,2),
    second_serve_points_won DECIMAL(5,2),
    break_points_saved DECIMAL(5,2),
    service_games_won DECIMAL(5,2),
    first_return_points_won DECIMAL(5,2),
    second_return_points_won DECIMAL(5,2),
    break_points_converted DECIMAL(5,2),
    return_games_won DECIMAL(5,2),
    tiebreaks_won INTEGER DEFAULT 0,
    tiebreaks_played INTEGER DEFAULT 0,
    deciding_sets_won INTEGER DEFAULT 0,
    deciding_sets_played INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(player_id, stat_date, surface, timeframe)
);
-- Add other tables from your schema here...
"""


class DatabaseInserter:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        logger.info(f"Database connection established to {self.db_path}")
        self._create_tables()

    def _create_tables(self):
        """Creates database tables if they don't exist."""
        try:
            with self.conn:
                self.conn.executescript(DB_SCHEMA)
            logger.info("Database schema verified and tables created if not exist.")
        except sqlite3.Error as e:
            logger.error(f"Database schema creation failed: {e}")
            raise

    def get_or_create_player(self, player_name: str) -> int:
        """Finds a player by name or creates a new entry, returning the player's ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM players WHERE name = ?", (player_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            logger.info(f"Creating new player: {player_name}")
            cursor.execute("INSERT INTO players (name) VALUES (?)", (player_name,))
            self.conn.commit()
            return cursor.lastrowid

    def insert_player_stats(self, items: List[StructuredDataItem], source_name: str):
        """
        Inserts player statistics from scraped data.
        This is a sample implementation for the 'atp_serve_leaderboard_52_week' source.
        """
        if source_name != "atp_serve_leaderboard_52_week":
            logger.warning(f"No specific insertion logic for source: {source_name}. Skipping.")
            return

        cursor = self.conn.cursor()
        total_inserted = 0
        from datetime import date

        for item in items:
            # The data is nested under the rule name from the YAML
            stats_list = item.structured_data.get("serve_stats_leaders", [])
            if not isinstance(stats_list, list): continue

            for stats in stats_list:
                try:
                    player_name = stats.get('player_name')
                    if not player_name: continue

                    player_id = self.get_or_create_player(player_name)

                    # A helper to clean and convert percentage strings like "70.5%" to 70.5
                    def clean_percent(val):
                        if isinstance(val, str):
                            return float(val.strip().replace('%', ''))
                        return val

                    # Prepare data for insertion
                    data_to_insert = {
                        "player_id": player_id,
                        "stat_date": date.today().isoformat(),
                        "surface": "all",
                        "timeframe": "last52weeks",
                        "matches_played": stats.get('matches_played'),
                        "first_serve_percentage": clean_percent(stats.get('first_serve_percentage')),
                        "first_serve_points_won": clean_percent(stats.get('first_serve_points_won')),
                        "second_serve_points_won": clean_percent(stats.get('second_serve_points_won')),
                        "service_games_won": clean_percent(stats.get('service_games_won')),
                        "aces_per_match": stats.get('aces_per_match'),  # Example data
                        "double_faults_per_match": stats.get('double_faults_per_match'),  # Example data
                    }

                    # Use INSERT OR REPLACE to handle UNIQUE constraints gracefully
                    # This will update the row if a record for that player/date/surface/timeframe already exists
                    columns = ', '.join(data_to_insert.keys())
                    placeholders = ', '.join('?' for _ in data_to_insert)
                    sql = f"INSERT OR REPLACE INTO player_statistics ({columns}) VALUES ({placeholders})"

                    cursor.execute(sql, tuple(data_to_insert.values()))
                    total_inserted += 1

                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping row due to data conversion error: {e}. Data: {stats}")
                except Exception as e:
                    logger.error(f"Error inserting stats row: {e}. Data: {stats}")

        self.conn.commit()
        logger.info(f"Successfully inserted/updated {total_inserted} rows into player_statistics.")

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")