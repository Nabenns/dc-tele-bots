import discord
from discord.ext import commands
import logging
import asyncio
import re
from typing import Optional, Dict, List, Any, Tuple

from database import Database
from telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('discord_bot')

class DiscordBot(commands.Bot):
    def __init__(self, command_prefix: str, telegram_bot: TelegramBot, database: Database):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix=command_prefix, intents=intents)
        
        self.telegram_bot = telegram_bot
        self.db = database
        self.add_commands()
        
        logger.info("Discord bot initialized")

    def add_commands(self):
        """Register all bot commands."""
        @self.command(name="forward")
        async def forward(ctx, action: str = None, *args):
            """
            Manage message forwarding to Telegram.
            
            Usage:
            !forward setup <telegram_chat_id> [topic_id] - Set up forwarding from current channel
            !forward setup @https://t.me/c/{chat_id}/{topic_id} - Setup using Telegram URL format
            !forward list - List all configured forwarding rules for this server
            !forward remove - Remove forwarding from current channel
            !forward help - Show this help message
            """
            if not action:
                await self.show_forward_help(ctx)
                return
                
            action = action.lower()
            
            if action == "setup":
                await self.setup_forwarding(ctx, args)
            elif action == "list":
                await self.list_forwarding(ctx)
            elif action == "remove":
                await self.remove_forwarding(ctx)
            elif action == "help":
                await self.show_forward_help(ctx)
            else:
                await ctx.send(f"Unknown action: `{action}`. Use `!forward help` for usage information.")

    def parse_telegram_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse a Telegram URL to extract chat ID and topic ID.
        
        Args:
            url: Telegram URL in format @https://t.me/c/{chat_id}/{topic_id} or similar
            
        Returns:
            Tuple[str, str]: (chat_id, topic_id) or (None, None) if parsing fails
        """
        try:
            # Remove @ prefix if present
            if url.startswith('@'):
                url = url[1:]
                
            # Extract chat ID and message/topic ID using regex
            pattern = r"https://t\.me/c/(\d+)/(\d+)"
            match = re.search(pattern, url)
            
            if match:
                chat_id = match.group(1)
                topic_id = match.group(2)
                
                # Telegram group IDs need to be negative and have -100 prefix
                # But we should NOT double-prefix if already prefixed
                if not chat_id.startswith('-'):
                    # Direct format without any prefix
                    chat_id = f"-100{chat_id}"
                elif chat_id.startswith('-100'):
                    # Already has the full prefix, keep as is
                    pass
                elif chat_id.startswith('-'):
                    # Has negative sign but not the prefix, add the 100
                    chat_id = f"-100{chat_id[1:]}"
                    
                logger.info(f"Parsed Telegram URL - Chat ID: {chat_id}, Topic ID: {topic_id}")
                
                # Remove any double prefixes that might have occurred
                if chat_id.startswith('-100-100'):
                    chat_id = chat_id.replace('-100-100', '-100')
                    logger.info(f"Fixed double prefix in chat ID, now: {chat_id}")
                    
                return chat_id, topic_id
            
            logger.error(f"Failed to parse Telegram URL: {url}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing Telegram URL: {e}")
            return None, None

    async def setup_forwarding(self, ctx, args):
        """Set up message forwarding for a channel."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return
            
        if len(args) < 1:
            await ctx.send("Please provide a Telegram chat ID or URL. Use `!forward help` for usage information.")
            return
        
        telegram_chat_id = None
        telegram_topic_id = None
        
        # Check if the argument is a Telegram URL
        first_arg = args[0]
        if first_arg.startswith('@https://t.me/') or first_arg.startswith('https://t.me/'):
            telegram_chat_id, telegram_topic_id = self.parse_telegram_url(first_arg)
            
            if not telegram_chat_id:
                await ctx.send("❌ Invalid Telegram URL format. Expected format: `@https://t.me/c/{chat_id}/{topic_id}`")
                return
                
            await ctx.send(f"Parsed Telegram URL: Chat ID: {telegram_chat_id}, Topic ID: {telegram_topic_id}")
        else:
            # Traditional format: separate chat_id and topic_id arguments
            telegram_chat_id = args[0]
            telegram_topic_id = args[1] if len(args) > 1 else None
        
        # Test the connection to Telegram
        await ctx.send("Testing connection to Telegram...")
        success = await self.telegram_bot.test_connection(telegram_chat_id, telegram_topic_id)
        
        if not success:
            await ctx.send("❌ Failed to connect to Telegram. Please check the chat ID and ensure the bot is a member of the chat.")
            return
            
        # Check if we can send messages with topic_id
        if telegram_topic_id:
            try:
                test_message = "🔄 Testing topic-specific message (ignore this test)"
                message_thread_id = int(telegram_topic_id)
                
                try:
                    await self.telegram_bot.bot.send_message(
                        chat_id=telegram_chat_id,
                        text=test_message,
                        message_thread_id=message_thread_id
                    )
                    logger.info(f"Topic-specific test succeeded for topic {telegram_topic_id}")
                except Exception as e:
                    logger.error(f"Topic-specific test failed: {e}")
                    
                    # Ask user if they want to continue without the topic
                    await ctx.send(f"⚠️ Warning: Could not send messages to topic {telegram_topic_id}. The bot can send messages to the main chat, but not to this specific topic.")
                    await ctx.send("Do you want to continue without a topic? Reply with `yes` to continue or `no` to cancel.")
                    
                    # Wait for response
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
                        
                    try:
                        msg = await self.wait_for('message', check=check, timeout=30.0)
                        if msg.content.lower() != "yes":
                            await ctx.send("Setup cancelled.")
                            return
                        
                        # If yes, continue without the topic_id
                        telegram_topic_id = None
                        await ctx.send("Continuing setup without a topic ID.")
                    except asyncio.TimeoutError:
                        await ctx.send("Setup timed out. Please try again.")
                        return
                        
            except ValueError:
                await ctx.send(f"⚠️ Warning: Topic ID '{telegram_topic_id}' is not a valid number. It will be ignored.")
                telegram_topic_id = None
            
        # Add the forwarding configuration to the database
        success = await self.db.add_forwarding_config(
            str(ctx.guild.id),
            str(ctx.channel.id),
            telegram_chat_id,
            telegram_topic_id
        )
        
        if success:
            destination = f"chat {telegram_chat_id}"
            if telegram_topic_id:
                destination += f", topic {telegram_topic_id}"
                
            await ctx.send(f"✅ Successfully set up forwarding from this channel to Telegram {destination}.")
        else:
            await ctx.send("❌ Failed to save forwarding configuration. Please try again.")

    async def list_forwarding(self, ctx):
        """List all forwarding configurations for the current guild."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return
            
        configs = await self.db.get_guild_forwarding_configs(str(ctx.guild.id))
        
        if not configs:
            await ctx.send("No forwarding configurations found for this server.")
            return
            
        embed = discord.Embed(
            title="Forwarding Configurations",
            color=discord.Color.blue(),
            description=f"Found {len(configs)} active forwarding configuration(s)."
        )
        
        for config in configs:
            channel = self.get_channel(int(config['discord_channel_id']))
            channel_name = channel.name if channel else "Unknown channel"
            
            destination = f"Chat: {config['telegram_chat_id']}"
            if config['telegram_topic_id']:
                destination += f"\nTopic: {config['telegram_topic_id']}"
                
            embed.add_field(
                name=f"#{channel_name}",
                value=destination,
                inline=False
            )
            
        await ctx.send(embed=embed)

    async def remove_forwarding(self, ctx):
        """Remove forwarding configuration for the current channel."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return
            
        success = await self.db.remove_forwarding_config(str(ctx.channel.id))
        
        if success:
            await ctx.send("✅ Forwarding configuration removed for this channel.")
        else:
            await ctx.send("❌ No forwarding configuration found for this channel or an error occurred.")

    async def show_forward_help(self, ctx):
        """Show help information for the forward command."""
        embed = discord.Embed(
            title="Forward Command Help",
            color=discord.Color.blue(),
            description="Manage message forwarding from Discord to Telegram"
        )
        
        embed.add_field(
            name="!forward setup <telegram_chat_id> [topic_id]",
            value="Set up forwarding from the current channel to a Telegram chat",
            inline=False
        )

        embed.add_field(
            name="!forward setup @https://t.me/c/{chat_id}/{topic_id}",
            value="Set up forwarding using a Telegram URL (recommended for supergroups with topics)",
            inline=False
        )
        
        embed.add_field(
            name="!forward list",
            value="List all configured forwarding rules for this server",
            inline=False
        )
        
        embed.add_field(
            name="!forward remove",
            value="Remove forwarding from the current channel",
            inline=False
        )
        
        embed.add_field(
            name="!forward help",
            value="Show this help message",
            inline=False
        )
        
        embed.add_field(
            name="Note",
            value="To get your Telegram chat URL, right-click on a message in the topic and select 'Copy Link'",
            inline=False
        )
        
        await ctx.send(embed=embed)

    async def on_ready(self):
        """Called when the bot is ready and connected to Discord."""
        logger.info(f"Connected to Discord as {self.user.name} ({self.user.id})")
        await self.change_presence(activity=discord.Game(name=f"!forward help"))

    async def on_message(self, message):
        """Called when a message is sent in any visible channel."""
        # Process commands only if it's a user message
        if not message.author.bot:
            await self.process_commands(message)
        
        # If not in a guild, ignore
        if not message.guild:
            return
            
        # Check if the channel is configured for forwarding
        config = await self.db.get_forwarding_config(str(message.channel.id))
        if not config:
            return
            
        # Don't forward command messages (starts with command prefix)
        if not message.author.bot and message.content.startswith(self.command_prefix):
            return
        
        # ONLY USE RAW CONTENT - no formatting, no author name
        # Extract just the pure message content
        content = message.content.strip() if message.content else ""
        
        # Get attachment URLs if any - we'll send these directly
        attachments = [attachment.url for attachment in message.attachments] if message.attachments else []
        
        # For images/attachments from discord apps/webhook/bots
        # Handle embeds if present - extract both content and images
        embed_text = ""
        embed_images = []
        if message.embeds:
            for embed in message.embeds:
                # For embeds, just extract the important content
                if embed.description:
                    embed_text += f"{embed.description.strip()}\n"
                
                # Extract images from embeds
                if embed.image and embed.image.url:
                    embed_images.append(embed.image.url)
                if embed.thumbnail and embed.thumbnail.url:
                    embed_images.append(embed.thumbnail.url)
                    
                # Extract images from fields if they contain URLs
                if embed.fields:
                    for field in embed.fields:
                        # Only extract field value if it might contain an image URL
                        if field.value and ('http://' in field.value or 'https://' in field.value):
                            # Extract URLs from the field
                            urls = self.extract_urls(field.value)
                            for url in urls:
                                if self.is_likely_image_url(url):
                                    embed_images.append(url)
            
            # Add embed text to content
            if embed_text:
                if content:
                    # Only add embed content if it's different from main content
                    if embed_text.strip() != content.strip():
                        content += "\n\n" + embed_text
                else:
                    content = embed_text
        
        # Add embed images to attachments
        if embed_images:
            attachments.extend(embed_images)
        
        # If no content and no attachments after processing, nothing to forward
        if not content and not attachments:
            return
            
        # Forward the message to Telegram
        try:
            logger.info(f"Forwarding message from Discord channel {message.channel.name} to Telegram chat {config['telegram_chat_id']}")
            logger.debug(f"Content: {content}")
            logger.debug(f"Attachments: {attachments}")
            
            success = await self.telegram_bot.forward_discord_message(
                chat_id=config['telegram_chat_id'],
                author=None,  # No longer sending author name
                content=content,
                topic_id=config['telegram_topic_id'],
                attachments=attachments
            )
            
            if success:
                logger.info(f"Successfully forwarded message to Telegram")
            else:
                logger.error(f"Failed to forward message to Telegram")
                
                # Check if this is the first failure for this channel and notify if so
                channel_key = f"forward_fail_{message.channel.id}"
                if not hasattr(self, channel_key):
                    setattr(self, channel_key, True)
                    
                    # Send an error message to the channel
                    error_msg = ("⚠️ Failed to forward messages to Telegram. "
                                "Please check that the bot has necessary permissions "
                                "and the chat/topic ID is correct. Use `!forward remove` "
                                "and set up again if needed.")
                    try:
                        await message.channel.send(error_msg)
                    except:
                        pass  # If we can't send the error message, just continue
        except Exception as e:
            logger.error(f"Error in message forwarding: {e}")
            # Continue processing to avoid breaking the bot
            
    def extract_urls(self, text):
        """Extract URLs from text."""
        if not text:
            return []
        # Simple URL regex pattern
        url_pattern = r'https?://[^\s<>"\']+'
        return re.findall(url_pattern, text)
        
    def is_likely_image_url(self, url):
        """Check if a URL is likely to point to an image."""
        if not url:
            return False
        # Check common image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        return any(url.lower().endswith(ext) for ext in image_extensions) 