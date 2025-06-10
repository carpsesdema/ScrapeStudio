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

    -- NEW: Additional fields to match your tennis data
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
        FIXED: Now handles the actual data structure from your scraper.
        """
        cursor = self.conn.cursor()
        total_inserted = 0
        from datetime import date

        logger.info(f"🔄 Processing {len(items)} structured data items...")

        for item in items:
            logger.info(f"📋 Processing item from {item.source_url}")
            logger.info(f"📋 Available structured data keys: {list(item.structured_data.keys())}")

            # FIXED: Find the actual data structure
            main_data_list = None

            # Look for the scraped table data
            for key, value in item.structured_data.items():
                logger.info(
                    f"   Key '{key}': {type(value)} with {len(value) if isinstance(value, list) else 'N/A'} items")
                if isinstance(value, list) and value:
                    main_data_list = value
                    logger.info(f"✅ Found data list under key '{key}' with {len(value)} records")
                    break

            if not main_data_list:
                logger.warning(f"❌ No structured list found in item from {item.source_url}")
                continue

            # Process each row from the table
            for i, row_data in enumerate(main_data_list):
                try:
                    if not isinstance(row_data, dict):
                        logger.warning(f"⚠️ Row {i} is not a dictionary: {type(row_data)}")
                        continue

                    logger.info(f"📊 Processing row {i}: {list(row_data.keys())}")

                    # FIXED: Extract player name from any available field
                    player_name = None
                    for name_field in ['player', 'player_name', 'elorank', 'name']:
                        if name_field in row_data and row_data[name_field]:
                            player_name = str(row_data[name_field]).strip()
                            break

                    # Try to get player name from the first non-empty field
                    if not player_name:
                        for key, value in row_data.items():
                            if value and isinstance(value, str) and len(value) > 1:
                                # Check if it looks like a name (contains letters)
                                if any(c.isalpha() for c in value):
                                    player_name = value.strip()
                                    logger.info(f"🎯 Using '{key}' as player name: {player_name}")
                                    break

                    if not player_name:
                        logger.warning(f"⚠️ No player name found in row {i}: {row_data}")
                        continue

                    player_id = self.get_or_create_player(player_name)

                    # FIXED: Map the actual field names from your scraper
                    def safe_convert_number(val, default=None):
                        """Safely convert a value to a number."""
                        if val is None or val == '':
                            return default
                        try:
                            # Remove any non-numeric characters except decimal point and minus
                            if isinstance(val, str):
                                cleaned = ''.join(c for c in val if c.isdigit() or c in '.-')
                                if cleaned and cleaned != '-':
                                    return float(cleaned)
                            return float(val)
                        except (ValueError, TypeError):
                            return default

                    # Create data mapping - using the field names from your table structure
                    data_to_insert = {
                        "player_id": player_id,
                        "player_name": player_name,
                        "stat_date": date.today().isoformat(),
                        "surface": "all",
                        "timeframe": "current",
                    }

                    # Map all the fields from your scraped data
                    field_mapping = {
                        'elorank': 'elo_rank',
                        'age': 'age',
                        'elo': 'elo_rating',
                        'helorank': 'helo_rank',
                        'helo': 'helo_rating',
                        'celorank': 'celo_rank',
                        'celo': 'celo_rating',
                        'gelorank': 'gelo_rank',
                        'gelo': 'gelo_rating',
                        'peakelo': 'peak_elo',
                        'peakmonth': 'peak_month',
                        'wtarank': 'wta_rank',
                        'logdiff': 'log_diff',
                        # Add more mappings as needed
                    }

                    # Apply the field mappings
                    for scraper_field, db_field in field_mapping.items():
                        if scraper_field in row_data:
                            value = row_data[scraper_field]
                            if db_field in ['age', 'elo_rating', 'helo_rating', 'celo_rating', 'gelo_rating',
                                            'peak_elo', 'log_diff']:
                                data_to_insert[db_field] = safe_convert_number(value)
                            elif db_field in ['elo_rank', 'helo_rank', 'celo_rank', 'gelo_rank', 'wta_rank']:
                                data_to_insert[db_field] = safe_convert_number(value, 0)
                            else:
                                data_to_insert[db_field] = str(value) if value else None

                    # Filter out None values
                    data_to_insert = {k: v for k, v in data_to_insert.items() if v is not None}

                    if len(data_to_insert) <= 4:  # Only basic fields
                        logger.warning(f"⚠️ Not enough data for row {i}: {data_to_insert}")
                        continue

                    # Insert into database
                    columns = ', '.join(data_to_insert.keys())
                    placeholders = ', '.join('?' for _ in data_to_insert)
                    sql = f"INSERT OR REPLACE INTO player_statistics ({columns}) VALUES ({placeholders})"

                    cursor.execute(sql, tuple(data_to_insert.values()))
                    total_inserted += 1

                    if total_inserted <= 5:  # Log first 5 for debugging
                        logger.info(f"✅ Inserted row {total_inserted}: {player_name} with {len(data_to_insert)} fields")

                except Exception as e:
                    logger.error(f"❌ Error processing row {i}: {e}")
                    logger.error(f"   Row data: {row_data}")

        self.conn.commit()
        logger.info(f"🎉 Successfully inserted/updated {total_inserted} rows into player_statistics.")
        return total_inserted

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")