# storage/database_inserter.py
"""
Handles saving structured data into the SQLite Tennis Intelligence Database.
"""
import sqlite3
import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import date

# Use the structured data model from the scraper
from scraper.rag_models import StructuredDataItem

logger = logging.getLogger(__name__)

DB_SCHEMA = """
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
    elo_rank INTEGER,
    player_name VARCHAR(200),
    age DECIMAL(4,1),
    elo_rating DECIMAL(6,1),
    helo_rank INTEGER,
    helo_rating DECIMAL(6,1),
    celo_rank INTEGER,
    celo_rating DECIMAL(6,1),
    gelo_rank INTEGER,
    gelo_rating DECIMAL(6,1),
    peak_elo DECIMAL(6,1),
    peak_month VARCHAR(20),
    wta_rank INTEGER,
    log_diff DECIMAL(4,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id),
    UNIQUE(player_id, stat_date)
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
        try:
            with self.conn:
                self.conn.executescript(DB_SCHEMA)
            logger.info("Database schema verified and tables created if not exist.")
        except sqlite3.Error as e:
            logger.error(f"Database schema creation failed: {e}")
            raise

    def get_or_create_player(self, player_name: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM players WHERE name = ?", (player_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            cursor.execute("INSERT INTO players (name) VALUES (?)", (player_name,))
            self.conn.commit()
            return cursor.lastrowid

    def insert_player_stats(self, items: List[StructuredDataItem]):
        cursor = self.conn.cursor()
        total_inserted = 0

        for item in items:
            main_data_list = None
            for key, value in item.structured_data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    main_data_list = value
                    break

            if not main_data_list:
                logger.warning(f"No structured list found in item from {item.source_url}. Skipping.")
                continue

            for row_data in main_data_list:
                try:
                    player_name_raw = row_data.get('player')
                    if not player_name_raw or not isinstance(player_name_raw, str):
                        continue

                    player_name = player_name_raw.strip()
                    if not player_name:
                        continue

                    player_id = self.get_or_create_player(player_name)

                    field_mapping = {
                        'elorank': 'elo_rank', 'player': 'player_name', 'age': 'age',
                        'elo': 'elo_rating', 'helorank': 'helo_rank', 'helo': 'helo_rating',
                        'celorank': 'celo_rank', 'celo': 'celo_rating', 'gelorank': 'gelo_rank',
                        'gelo': 'gelo_rating', 'peakelo': 'peak_elo', 'peakmonth': 'peak_month',
                        'wtarank': 'wta_rank', 'logdiff': 'log_diff',
                    }

                    def safe_convert_number(val, default=None):
                        if val is None or val == '':
                            return default
                        try:
                            if isinstance(val, str):
                                cleaned = ''.join(c for c in val if c.isdigit() or c in '.-')
                                if cleaned in ('', '.', '-'):
                                    return default
                                return float(cleaned)
                            return float(val)
                        except (ValueError, TypeError):
                            return default

                    data_to_insert = {
                        "player_id": player_id,
                        "stat_date": date.today().isoformat()
                    }

                    for scraped_field, db_column in field_mapping.items():
                        if scraped_field in row_data and row_data[scraped_field] is not None:
                            value = row_data[scraped_field]
                            # Use a clearer type-based conversion
                            if 'rank' in db_column:
                                data_to_insert[db_column] = int(safe_convert_number(value, 0))
                            elif any(x in db_column for x in ['rating', 'elo', 'age', 'diff']):
                                data_to_insert[db_column] = safe_convert_number(value)
                            else:  # For strings like player_name and peak_month
                                data_to_insert[db_column] = str(value).strip()

                    # Filter out any keys that didn't get a value
                    final_data = {k: v for k, v in data_to_insert.items() if v is not None}

                    if len(final_data) <= 2:  # player_id and stat_date
                        logger.warning(f"Not enough valid data to insert for player {player_name}")
                        continue

                    columns = ', '.join(final_data.keys())
                    placeholders = ', '.join('?' for _ in final_data)
                    sql = f"INSERT OR REPLACE INTO player_statistics ({columns}) VALUES ({placeholders})"

                    cursor.execute(sql, tuple(final_data.values()))
                    total_inserted += 1

                except Exception as e:
                    logger.error(f"FATAL DB ERROR on row for '{row_data.get('player', 'UNKNOWN')}': {e}", exc_info=True)
                    logger.error(f"Problematic row data: {row_data}")

        self.conn.commit()
        logger.info(f"DB INSERT COMPLETE: {total_inserted} rows successfully inserted/updated.")
        return total_inserted

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")