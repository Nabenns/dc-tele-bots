import aiosqlite
import os
import logging
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('database')

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"Database initialized with path: {db_path}")

    async def init_db(self):
        """Initialize database and create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Create forwarding_config table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS forwarding_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_guild_id TEXT NOT NULL,
                    discord_channel_id TEXT NOT NULL,
                    telegram_chat_id TEXT NOT NULL,
                    telegram_topic_id TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(discord_channel_id)
                )
            ''')
            await db.commit()
            logger.info("Database initialized successfully")

    async def add_forwarding_config(self, discord_guild_id: str, discord_channel_id: str, 
                             telegram_chat_id: str, telegram_topic_id: Optional[str] = None) -> bool:
        """Add or update a forwarding configuration."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if config already exists
                async with db.execute(
                    'SELECT id FROM forwarding_config WHERE discord_channel_id = ?', 
                    (discord_channel_id,)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing config
                    await db.execute(
                        '''
                        UPDATE forwarding_config 
                        SET telegram_chat_id = ?, telegram_topic_id = ?, enabled = 1
                        WHERE discord_channel_id = ?
                        ''',
                        (telegram_chat_id, telegram_topic_id, discord_channel_id)
                    )
                    logger.info(f"Updated forwarding config for Discord channel {discord_channel_id}")
                else:
                    # Insert new config
                    await db.execute(
                        '''
                        INSERT INTO forwarding_config 
                        (discord_guild_id, discord_channel_id, telegram_chat_id, telegram_topic_id)
                        VALUES (?, ?, ?, ?)
                        ''',
                        (discord_guild_id, discord_channel_id, telegram_chat_id, telegram_topic_id)
                    )
                    logger.info(f"Added new forwarding config for Discord channel {discord_channel_id}")
                
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding forwarding config: {e}")
            return False

    async def remove_forwarding_config(self, discord_channel_id: str) -> bool:
        """Remove a forwarding configuration."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'DELETE FROM forwarding_config WHERE discord_channel_id = ?',
                    (discord_channel_id,)
                )
                await db.commit()
                logger.info(f"Removed forwarding config for Discord channel {discord_channel_id}")
                return True
        except Exception as e:
            logger.error(f"Error removing forwarding config: {e}")
            return False

    async def get_forwarding_config(self, discord_channel_id: str) -> Optional[Dict]:
        """Get forwarding configuration for a Discord channel."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    '''
                    SELECT * FROM forwarding_config 
                    WHERE discord_channel_id = ? AND enabled = 1
                    ''',
                    (discord_channel_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Error getting forwarding config: {e}")
            return None

    async def get_all_forwarding_configs(self) -> List[Dict]:
        """Get all active forwarding configurations."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    'SELECT * FROM forwarding_config WHERE enabled = 1'
                ) as cursor:
                    rows = await cursor.fetchall()
                    
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all forwarding configs: {e}")
            return []

    async def get_guild_forwarding_configs(self, discord_guild_id: str) -> List[Dict]:
        """Get all active forwarding configurations for a specific guild."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    '''
                    SELECT * FROM forwarding_config 
                    WHERE discord_guild_id = ? AND enabled = 1
                    ''',
                    (discord_guild_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting guild forwarding configs: {e}")
            return [] 