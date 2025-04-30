import os
import logging
import asyncio
from dotenv import load_dotenv
import sys
import signal

from database import Database
from telegram_bot import TelegramBot
from discord_bot import DiscordBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('main')

# Load environment variables
load_dotenv()

class Bot:
    def __init__(self):
        """Initialize the bot application."""
        # Get configuration from environment variables
        self.discord_token = os.getenv('DISCORD_TOKEN')
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.db_path = os.getenv('DATABASE_PATH', 'config/bot_config.db')
        self.command_prefix = os.getenv('COMMAND_PREFIX', '!')
        
        # Check if tokens are provided
        if not self.discord_token:
            logger.error("Discord token not found. Please set DISCORD_TOKEN in .env file.")
            sys.exit(1)
            
        if not self.telegram_token:
            logger.error("Telegram token not found. Please set TELEGRAM_TOKEN in .env file.")
            sys.exit(1)
            
        # Ensure the config directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize components
        self.db = Database(self.db_path)
        self.telegram_bot = TelegramBot(self.telegram_token)
        self.discord_bot = DiscordBot(self.command_prefix, self.telegram_bot, self.db)
        
        logger.info("Bot application initialized")
        
    async def start(self):
        """Start the bot application."""
        try:
            # Initialize the database
            await self.db.init_db()
            
            # Start the Discord bot
            logger.info("Starting Discord bot...")
            await self.discord_bot.start(self.discord_token)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt. Shutting down...")
            await self.stop()
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            await self.stop()
            
    async def stop(self):
        """Stop the bot application."""
        try:
            if self.discord_bot:
                logger.info("Closing Discord connection...")
                await self.discord_bot.close()
                
            if hasattr(self, 'telegram_bot') and self.telegram_bot:
                logger.info("Closing Telegram bot resources...")
                await self.telegram_bot.close()
                
            logger.info("Bot shutdown complete.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def handle_sigterm(signum, frame):
    """Handle SIGTERM signal."""
    logger.info("Received SIGTERM. Shutting down...")
    raise KeyboardInterrupt

async def main():
    """Main entry point for the application."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    bot = Bot()
    await bot.start()

if __name__ == "__main__":
    # Run the bot
    try:
        logger.info("Starting Discord to Telegram forwarder bot...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        sys.exit(1) 