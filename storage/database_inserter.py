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
-- The full DB schema from before, omitted for brevity
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

    def insert_player_stats(self, items: List[StructuredDataItem]):
        """
        Inserts player statistics from scraped data.
        This implementation is now generic and works for any project that scrapes player stats.
        """
        cursor = self.conn.cursor()
        total_inserted = 0
        from datetime import date

        for item in items:
            # --- INTELLIGENT DATA FINDER ---
            # Find the first field in the data that is a list of dictionaries (our structured list)
            stats_list = []
            for key, value in item.structured_data.items():
                if isinstance(value, list) and all(isinstance(i, dict) for i in value):
                    stats_list = value
                    logger.info(f"Found structured list to process under key: '{key}'")
                    break

            if not stats_list:
                logger.warning(f"No structured list found in item from {item.source_url}. Skipping.")
                continue

            for stats_row in stats_list:
                try:
                    # Use .get() to safely access keys that might be missing
                    player_name = stats_row.get('player') or stats_row.get('player_name')
                    if not player_name: continue

                    player_id = self.get_or_create_player(player_name)

                    def clean_percent(val):
                        if isinstance(val, str): return float(val.strip().replace('%', ''))
                        return val

                    # Map data from the scrape to the DB columns
                    data_to_insert = {
                        "player_id": player_id,
                        "stat_date": date.today().isoformat(),
                        "surface": "all",  # This could be parameterized in the future
                        "timeframe": "last52weeks",  # This could also be parameterized
                        "matches_played": stats_row.get('matches_played'),
                        "first_serve_percentage": clean_percent(stats_row.get('first_serve_percentage')),
                        "first_serve_points_won": clean_percent(stats_row.get('first_serve_points_won')),
                        "second_serve_points_won": clean_percent(stats_row.get('second_serve_points_won')),
                        "service_games_won": clean_percent(stats_row.get('service_games_won')),
                        # Add other mappings here as you create rules for them
                    }

                    # Filter out None values so they don't overwrite DB defaults
                    data_to_insert = {k: v for k, v in data_to_insert.items() if v is not None}

                    if not data_to_insert: continue

                    columns = ', '.join(data_to_insert.keys())
                    placeholders = ', '.join('?' for _ in data_to_insert)
                    sql = f"INSERT OR REPLACE INTO player_statistics ({columns}) VALUES ({placeholders})"

                    cursor.execute(sql, tuple(data_to_insert.values()))
                    total_inserted += 1

                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping row due to data conversion error: {e}. Data: {stats_row}")
                except Exception as e:
                    logger.error(f"Error inserting stats row: {e}. Data: {stats_row}")

        self.conn.commit()
        logger.info(f"Successfully inserted/updated {total_inserted} rows into player_statistics.")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")