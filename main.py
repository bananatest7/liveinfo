import os
import requests
import json
import time
import asyncio
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from bs4 import BeautifulSoup
from datetime import datetime
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TangoScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def get_live_broadcasters(self) -> List[Dict]:
        """Scrape live broadcasters from Tango.me"""
        try:
            url = "https://www.tango.me/live/nearby"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            broadcasters = []
            
            # Look for broadcaster containers (adjust selectors based on actual HTML structure)
            broadcaster_elements = soup.find_all('div', class_=['broadcaster-card', 'live-stream-card', 'stream-item'])
            
            for element in broadcaster_elements:
                broadcaster_data = self._extract_broadcaster_data(element)
                if broadcaster_data:
                    broadcasters.append(broadcaster_data)
            
            return broadcasters
            
        except Exception as e:
            logger.error(f"Error scraping live broadcasters: {e}")
            return []
    
    def _extract_broadcaster_data(self, element) -> Optional[Dict]:
        """Extract data from a broadcaster element"""
        try:
            data = {}
            
            # Extract username (adjust selectors based on actual HTML)
            username_elem = element.find(['span', 'div', 'h3'], class_=['username', 'broadcaster-name', 'name'])
            data['username'] = username_elem.text.strip() if username_elem else "Unknown"
            
            # Extract viewer count
            viewers_elem = element.find(['span', 'div'], class_=['viewers', 'viewer-count', 'live-count'])
            data['viewers'] = self._extract_number(viewers_elem.text if viewers_elem else "0")
            
            # Extract profile image
            img_elem = element.find('img')
            data['profile_image'] = img_elem.get('src') if img_elem else None
            
            # Extract stream title/description
            title_elem = element.find(['span', 'div', 'p'], class_=['title', 'stream-title', 'description'])
            data['title'] = title_elem.text.strip() if title_elem else ""
            
            # Extract profile link
            link_elem = element.find('a') or element.find(['div', 'span'], {'data-href': True})
            if link_elem:
                href = link_elem.get('href') or link_elem.get('data-href')
                data['profile_url'] = f"https://www.tango.me{href}" if href and href.startswith('/') else href
            
            # Extract additional metrics
            data['timestamp'] = datetime.now().isoformat()
            data['is_live'] = True
            
            return data if data['username'] != "Unknown" else None
            
        except Exception as e:
            logger.error(f"Error extracting broadcaster data: {e}")
            return None
    
    def _extract_number(self, text: str) -> int:
        """Extract number from text (e.g., '1.2K viewers' -> 1200)"""
        try:
            import re
            numbers = re.findall(r'[\d.]+', text)
            if numbers:
                num = float(numbers[0])
                if 'k' in text.lower():
                    num *= 1000
                elif 'm' in text.lower():
                    num *= 1000000
                return int(num)
        except:
            pass
        return 0
    
    def get_broadcaster_profile(self, username: str) -> Optional[Dict]:
        """Get detailed profile information for a specific broadcaster"""
        try:
            url = f"https://www.tango.me/{username}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            profile_data = {
                'username': username,
                'followers': 0,
                'following': 0,
                'total_streams': 0,
                'bio': "",
                'profile_image': "",
                'is_verified': False,
                'last_seen': "",
                'timestamp': datetime.now().isoformat()
            }
            
            # Extract profile stats (adjust selectors based on actual HTML)
            stats_elements = soup.find_all(['span', 'div'], class_=['stat', 'count', 'number'])
            for stat in stats_elements:
                text = stat.text.lower()
                if 'follower' in text:
                    profile_data['followers'] = self._extract_number(stat.text)
                elif 'following' in text:
                    profile_data['following'] = self._extract_number(stat.text)
            
            # Extract bio
            bio_elem = soup.find(['div', 'p'], class_=['bio', 'description', 'about'])
            if bio_elem:
                profile_data['bio'] = bio_elem.text.strip()
            
            # Extract profile image
            img_elem = soup.find('img', class_=['profile-pic', 'avatar', 'profile-image'])
            if img_elem:
                profile_data['profile_image'] = img_elem.get('src')
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error getting broadcaster profile: {e}")
            return None

class TangoBroadcasterBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.scraper = TangoScraper()
        self.setup_handlers()
        
    def setup_handlers(self):
        """Setup command and callback handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("live", self.live_broadcasters_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("top", self.top_broadcasters_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        welcome_text = """
🎥 **Tango.me Broadcaster Data Bot** 🎥

Available commands:
/live - Get current live broadcasters
/profile <username> - Get broadcaster profile info
/top - Get top broadcasters by viewers
/help - Show this help message

Click the buttons below to get started!
        """
        
        keyboard = [
            [InlineKeyboardButton("🔴 Live Broadcasters", callback_data="live")],
            [InlineKeyboardButton("🏆 Top Broadcasters", callback_data="top")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def live_broadcasters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get current live broadcasters"""
        await update.message.reply_text("🔍 Fetching live broadcasters...")
        
        broadcasters = self.scraper.get_live_broadcasters()
        
        if not broadcasters:
            await update.message.reply_text("❌ No live broadcasters found or error occurred.")
            return
        
        # Sort by viewer count
        broadcasters.sort(key=lambda x: x.get('viewers', 0), reverse=True)
        
        message = "🔴 **Current Live Broadcasters:**\n\n"
        
        for i, broadcaster in enumerate(broadcasters[:10], 1):  # Show top 10
            username = broadcaster.get('username', 'Unknown')
            viewers = broadcaster.get('viewers', 0)
            title = broadcaster.get('title', '')
            
            message += f"{i}. **{username}**\n"
            message += f"   👥 {viewers:,} viewers\n"
            if title:
                message += f"   📝 {title[:50]}{'...' if len(title) > 50 else ''}\n"
            message += "\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="live")],
            [InlineKeyboardButton("🏆 Top Broadcasters", callback_data="top")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get broadcaster profile information"""
        if not context.args:
            await update.message.reply_text("❌ Please provide a username: /profile <username>")
            return
        
        username = context.args[0].replace('@', '')
        await update.message.reply_text(f"🔍 Fetching profile for {username}...")
        
        profile = self.scraper.get_broadcaster_profile(username)
        
        if not profile:
            await update.message.reply_text(f"❌ Could not find profile for {username}")
            return
        
        message = f"👤 **Profile: {profile['username']}**\n\n"
        message += f"👥 Followers: {profile['followers']:,}\n"
        message += f"➡️ Following: {profile['following']:,}\n"
        
        if profile['bio']:
            message += f"📝 Bio: {profile['bio'][:200]}{'...' if len(profile['bio']) > 200 else ''}\n"
        
        message += f"🕐 Last updated: {profile['timestamp'][:19]}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def top_broadcasters_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get top broadcasters by viewer count"""
        await update.message.reply_text("🔍 Fetching top broadcasters...")
        
        broadcasters = self.scraper.get_live_broadcasters()
        
        if not broadcasters:
            await update.message.reply_text("❌ No broadcasters found.")
            return
        
        # Sort by viewer count
        top_broadcasters = sorted(broadcasters, key=lambda x: x.get('viewers', 0), reverse=True)[:5]
        
        message = "🏆 **Top 5 Broadcasters by Viewers:**\n\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        
        for i, broadcaster in enumerate(top_broadcasters):
            username = broadcaster.get('username', 'Unknown')
            viewers = broadcaster.get('viewers', 0)
            title = broadcaster.get('title', '')
            
            message += f"{medals[i]} **{username}**\n"
            message += f"   👥 {viewers:,} viewers\n"
            if title:
                message += f"   📝 {title[:40]}{'...' if len(title) > 40 else ''}\n"
            message += "\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="top")],
            [InlineKeyboardButton("🔴 All Live", callback_data="live")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "live":
            await self.live_broadcasters_command(update, context)
        elif query.data == "top":
            await self.top_broadcasters_command(update, context)
        elif query.data == "help":
            help_text = """
🎥 **Tango.me Broadcaster Bot Help**

**Commands:**
/start - Start the bot
/live - Get current live broadcasters
/profile <username> - Get detailed profile info
/top - Get top 5 broadcasters by viewers

**Features:**
• Real-time live broadcaster data
• Viewer count tracking
• Profile information
• Top broadcaster rankings

**Note:** Data is scraped from public Tango.me pages.
            """
            await query.edit_message_text(help_text, parse_mode='Markdown')
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Tango Broadcaster Bot...")
        self.application.run_polling()

def main():
    # Get bot token from environment variable
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN environment variable not set!")
        print("Please set your Telegram bot token as an environment variable:")
        print("export BOT_TOKEN='your_bot_token_here'")
        return
    
    # Create and run bot
    bot = TangoBroadcasterBot(BOT_TOKEN)
    bot.run()

if __name__ == '__main__':
    main()
