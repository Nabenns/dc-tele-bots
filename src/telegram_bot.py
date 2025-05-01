import logging
import asyncio
import io
import re
import aiohttp
from typing import Optional, Dict, Any, List

from telegram import Bot, InputFile
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_bot')

class TelegramBot:
    def __init__(self, token: str):
        """Initialize the Telegram bot with the given token."""
        self.bot = Bot(token)
        self.session = aiohttp.ClientSession()
        logger.info("Telegram bot initialized")
        
    async def close(self):
        """Close resources when bot is shutting down."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def send_message(self, chat_id: str, text: str, 
                          topic_id: Optional[str] = None, **kwargs) -> bool:
        """
        Send a message to a Telegram chat.
        
        Args:
            chat_id: The chat ID where to send the message
            text: The text to send
            topic_id: Optional topic ID for supergroups
            **kwargs: Additional parameters to pass to the send_message method
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            params = {'chat_id': chat_id, 'text': text, **kwargs}
            
            # Add message_thread_id if topic_id is provided
            if topic_id:
                # Make sure topic_id is an integer
                try:
                    message_thread_id = int(topic_id)
                    params['message_thread_id'] = message_thread_id
                    logger.info(f"Using message_thread_id: {message_thread_id}")
                except ValueError:
                    logger.warning(f"Invalid topic_id format: {topic_id}, should be an integer. Skipping thread ID.")
            
            logger.info(f"Sending message to Telegram - Chat ID: {chat_id}, Params: {params}")
            await self.bot.send_message(**params)
            logger.info(f"Message successfully sent to Telegram chat {chat_id}")
            return True
        except TelegramError as e:
            logger.error(f"Error sending message to Telegram: {e}")
            return False
            
    async def is_image_url(self, url: str) -> bool:
        """Check if URL points to an image by examining the extension or content type."""
        # Check by extension first
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        
        # Discord and other common image hosting URLs
        image_hosts = [
            'media.discordapp.net', 'cdn.discordapp.com', 'i.imgur.com', 
            'images-ext-', 'images-', '.staticflickr.com', 'i.gyazo.com',
            'pbs.twimg.com', 'i.redd.it', 'preview.redd.it', 'tradingview.com'
        ]
        
        # Quick check for common image hosts and extensions
        url_lower = url.lower()
        if any(ext in url_lower for ext in image_extensions):
            return True
        if any(host in url_lower for host in image_hosts):
            return True
            
        # If not clear from URL pattern, check by requesting headers
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with self.session.head(url, allow_redirects=True, timeout=5, headers=headers) as response:
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '')
                    return content_type.startswith('image/')
                return False
        except Exception as e:
            logger.warning(f"Error checking if URL is image (treating as non-image): {e}")
            return False
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download an image from URL."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with self.session.get(url, timeout=15, headers=headers) as response:
                if response.status == 200:
                    image_data = await response.read()
                    # Log size for debugging
                    logger.info(f"Downloaded image: {len(image_data)} bytes")
                    return image_data
                else:
                    logger.error(f"Failed to download image, status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    async def forward_discord_message(self, chat_id: str, author: Optional[str] = None, content: str = "",
                                    topic_id: Optional[str] = None,
                                    attachments: Optional[list] = None) -> bool:
        """
        Forward a Discord message to Telegram.
        
        Args:
            chat_id: Telegram chat ID
            author: Discord author name, or None to not include author
            content: Message content
            topic_id: Optional topic ID for supergroups
            attachments: List of attachment URLs
            
        Returns:
            bool: True if forwarded successfully, False otherwise
        """
        try:
            # Skip if no content and no attachments
            if not content and not (attachments and len(attachments) > 0):
                logger.warning("No content or attachments to forward")
                return False
                
            # Use content as is - no additional formatting
            formatted_message = content
            
            # Handle character limit for Telegram messages (4096 chars)
            if len(formatted_message) > 4000:
                formatted_message = formatted_message[:3997] + "..."
            
            # Initialize success
            message_success = False
            attachment_success = False
            
            # Log what we're processing
            logger.info(f"Processing message with {len(attachments) if attachments else 0} attachments")
            if attachments:
                logger.debug(f"Attachment URLs: {attachments}")
            
            # First, process attachments - especially images
            if attachments:
                for url in attachments:
                    try:
                        # Check if it's an image URL
                        is_image = await self.is_image_url(url)
                        logger.info(f"URL: {url} - Is image: {is_image}")
                        
                        if is_image:
                            # Download the image
                            logger.info(f"Downloading image from {url}")
                            image_data = await self.download_image(url)
                            
                            if image_data and len(image_data) > 0:
                                # If we have text content, send it with the first image only if needed
                                if not message_success and formatted_message:
                                    try:
                                        # Create a BytesIO object from the image data
                                        photo = io.BytesIO(image_data)
                                        photo.name = 'image.jpg'  # Add a filename
                                        
                                        # Send photo with caption
                                        if topic_id:
                                            await self.bot.send_photo(
                                                chat_id=chat_id,
                                                photo=photo,
                                                # Only add caption if the image doesn't describe itself
                                                caption=formatted_message if not self.url_in_content(formatted_message, url) else None,
                                                message_thread_id=int(topic_id),
                                                parse_mode=None  # No markdown/HTML parsing
                                            )
                                        else:
                                            await self.bot.send_photo(
                                                chat_id=chat_id,
                                                photo=photo,
                                                # Only add caption if the image doesn't describe itself
                                                caption=formatted_message if not self.url_in_content(formatted_message, url) else None,
                                                parse_mode=None  # No markdown/HTML parsing
                                            )
                                            
                                        # Mark message as sent successfully
                                        message_success = True
                                        attachment_success = True
                                        logger.info(f"Sent image with caption")
                                    except Exception as e:
                                        logger.error(f"Failed to send image with caption: {e}")
                                        # Continue to try sending text separately
                                else:
                                    # Just send the image without caption
                                    try:
                                        photo = io.BytesIO(image_data)
                                        photo.name = 'image.jpg'
                                        
                                        if topic_id:
                                            await self.bot.send_photo(
                                                chat_id=chat_id,
                                                photo=photo,
                                                message_thread_id=int(topic_id)
                                            )
                                        else:
                                            await self.bot.send_photo(
                                                chat_id=chat_id,
                                                photo=photo
                                            )
                                            
                                        attachment_success = True
                                        logger.info(f"Sent image without caption")
                                    except Exception as e:
                                        logger.error(f"Failed to send image: {e}")
                                        # If we can't send as photo, try sending URL
                                        await self.send_attachment_url(chat_id, url, topic_id)
                            else:
                                logger.warning(f"Image data empty or download failed, sending URL instead")
                                # Fallback to URL if download failed
                                await self.send_attachment_url(chat_id, url, topic_id)
                                attachment_success = True
                        else:
                            # Not a recognized image, send as URL
                            logger.info(f"Not recognized as image, sending as URL: {url}")
                            await self.send_attachment_url(chat_id, url, topic_id)
                            attachment_success = True
                    except Exception as e:
                        logger.error(f"Error processing attachment: {e}")
                        # Try to continue with other attachments
            
            # If we still need to send the text message
            if formatted_message and not message_success:
                text_success = await self.send_text_message(chat_id, formatted_message, topic_id)
                message_success = text_success
            
            # Overall success if either message or attachment was sent successfully
            return message_success or attachment_success
        except Exception as e:
            logger.error(f"Error forwarding Discord message to Telegram: {e}")
            return False
            
    def url_in_content(self, content: str, url: str) -> bool:
        """Check if URL is already contained in the content."""
        if not content or not url:
            return False
        # Simplify URL for comparison
        simple_url = url.split('?')[0]  # Remove query params
        simple_url = simple_url.split('/')[-1]  # Get filename
        return simple_url in content

    async def send_text_message(self, chat_id: str, text: str, topic_id: Optional[str] = None) -> bool:
        """Send a text message to Telegram."""
        try:
            # Skip empty messages
            if not text or not text.strip():
                return False
            
            # Try sending with topic_id first if provided
            if topic_id:
                try:
                    message_thread_id = int(topic_id)
                    logger.info(f"Sending text message to chat {chat_id} with topic {topic_id}")
                    
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        message_thread_id=message_thread_id,
                        parse_mode=None  # No markdown/HTML parsing
                    )
                    logger.info(f"Text message sent to topic {topic_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to send text to topic {topic_id}: {e}")
                    logger.info(f"Falling back to sending without topic ID")
                    # Continue to try without topic_id
            
            # Try without topic_id
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=None  # No markdown/HTML parsing
                )
                logger.info(f"Text message sent to main chat")
                return True
            except Exception as e:
                logger.error(f"Failed to send text to main chat: {e}")
                return False
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            return False
    
    async def send_attachment_url(self, chat_id: str, url: str, topic_id: Optional[str] = None) -> bool:
        """Send an attachment URL to Telegram."""
        try:
            attachment_msg = f"Attachment: {url}"
            
            if topic_id:
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=attachment_msg,
                        message_thread_id=int(topic_id)
                    )
                    return True
                except Exception:
                    # If sending to topic fails, try without topic
                    logger.info(f"Failed to send attachment to topic, trying main chat")
                    pass
                    
            # Send to main chat
            await self.bot.send_message(
                chat_id=chat_id,
                text=attachment_msg
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send attachment URL: {e}")
            return False

    async def test_connection(self, chat_id: str, topic_id: Optional[str] = None) -> bool:
        """
        Test the connection to the Telegram chat.
        
        Args:
            chat_id: The chat ID to test
            topic_id: Optional topic ID for supergroups
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First try to get chat information to verify the bot is a member
            try:
                logger.info(f"Testing connection to Telegram chat {chat_id}")
                chat = await self.bot.get_chat(chat_id)
                logger.info(f"Successfully connected to chat: {chat.title if hasattr(chat, 'title') else chat.id}")
                
                # Check if the chat is a supergroup if topic_id is provided
                if topic_id and hasattr(chat, 'type'):
                    if chat.type != 'supergroup':
                        logger.warning(f"Chat {chat_id} is not a supergroup but topic_id was provided. Topics are only available in supergroups.")
            except Exception as e:
                logger.error(f"Failed to get chat information: {e}")
                return False
                
            # First try sending a message without topic_id to verify basic permissions
            basic_test_message = "🔄 Checking basic permission to send messages (ignore this test)"
            
            logger.info(f"Testing basic message sending ability without thread ID")
            basic_success = False
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=basic_test_message
                )
                logger.info(f"Successfully sent basic test message to Telegram chat {chat_id}")
                basic_success = True
            except Exception as e:
                logger.error(f"Failed to send basic test message: {e}")
                return False
                
            # If no topic_id or basic test succeeded, we're done
            if not topic_id or not basic_success:
                return basic_success
                
            # Now try with the topic_id
            logger.info(f"Testing message sending with thread ID {topic_id}")
            thread_test_message = "🔄 Testing topic-specific messaging (ignore this test)"
            
            # For topic testing, use the direct bot.send_message to avoid our wrapper
            try:
                message_thread_id = int(topic_id)
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=thread_test_message,
                    message_thread_id=message_thread_id
                )
                logger.info(f"Successfully sent test message to topic {topic_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to send message to topic {topic_id}: {e}")
                logger.warning("Topic-specific messaging failed, but the bot can still send messages to the main chat")
                
                # If we can send to the main chat but not the topic, suggest to the user
                # that we'll set up forwarding without a topic
                return True  # Return True because we can still forward to the main chat
                
        except Exception as e:
            logger.error(f"Error testing connection to Telegram: {e}")
            return False 