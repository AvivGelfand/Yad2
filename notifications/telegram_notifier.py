import requests
import json
import re
import pandas as pd
from typing import List, Dict, Optional
import logging
from datetime import datetime


# Strip quote/gershayim chars + collapse whitespace so Hebrew names match
# regardless of ״/"/' variants (e.g. גן רש״ל vs גן רש"ל).
_STRIP_QUOTES = str.maketrans("", "", "\"'׳״‘’“”")


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).translate(_STRIP_QUOTES).strip()


# Neighborhoods we never want notifications about.
BLOCKED_NEIGHBORHOODS = {_norm(n) for n in ("יד התשעה", "גן רש\"ל", "נווה עמל")}

# Neighborhoods close to the train station — flagged with 👍. Add more here.
TRAIN_CLOSE_NEIGHBORHOODS = {_norm(n) for n in ("נווה ישראל", "מרכז")}

# Free-text signals for a shelter in the building (when there is no ממ״ד).
_SHELTER_TEXT_SIGNS = ("מקלט", "מרחב מוגן")


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Bot token from BotFather
            chat_id: Chat ID where messages will be sent
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Test the connection
        if not self.test_connection():
            raise ConnectionError("Failed to connect to Telegram API")
    
    def test_connection(self) -> bool:
        """Test if the bot token and chat ID are valid"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Telegram connection test failed: {e}")
            return False
    
    def send_message(self, message: str) -> bool:
        """
        Send a text message to the configured chat
        
        Args:
            message: Message text to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                logging.info("Message sent successfully to Telegram")
                return True
            else:
                logging.error(f"Failed to send message: {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")
            return False
    
    def format_property_message(self, property_data: Dict) -> str:
        """
        Format property data into a readable message
        
        Args:
            property_data: Dictionary containing property information
            
        Returns:
            str: Formatted message
        """
        # Extract key information - Updated to match your scraper's field names
        price = property_data.get('rent', 'N/A')  # Changed from 'price_ils' to 'rent'
        city = property_data.get('city', 'N/A')
        neighborhood = property_data.get('neighborhood', 'N/A')
        street = property_data.get('street', 'N/A')
        rooms = property_data.get('rooms', 'N/A')
        area = property_data.get('sqm', 'N/A')  # Changed from 'area_sqm' to 'sqm'
        floor = property_data.get('floor', 'N/A')
        elevator = property_data.get('elevator', None)
        balcony = property_data.get('balcony', None)
        url = property_data.get('link', '')
        
        # Format price
        if isinstance(price, (int, float)) and price > 0:
            price_formatted = f"₪{price:,.0f}"
        else:
            price_formatted = "Price not specified"
        
        # Format elevator / balcony info: anything not explicitly True is No.
        elevator_text = "✅ Yes" if elevator is True else "❌ No"
        balcony_text = "✅ Yes" if balcony is True else "❌ No"

        # 👍 next to neighborhoods close to the train station.
        neighborhood_display = neighborhood
        if _norm(neighborhood) in TRAIN_CLOSE_NEIGHBORHOODS:
            neighborhood_display = f"{neighborhood} 👍"

        # 🚀 Protection: ממ״ד is best (👍); otherwise a shelter in the building.
        if property_data.get('mamad') is True:
            protection_text = "✅👍 ממ״ד"
        elif self._has_shelter_text(property_data):
            protection_text = "✅ מקלט בבניין"
        else:
            protection_text = "❌ אין ממ״ד/מקלט"

        # Build message
        message = f"""🏠 <b>New Property Found!</b>

💰 <b>Rent:</b> {price_formatted}
📍 <b>Location:</b> {street}, {neighborhood_display}
🏠 <b>Rooms:</b> {rooms}
📐 <b>Area:</b> {area} sqm
🏢 <b>Floor:</b> {floor}
🛗 <b>Elevator:</b> {elevator_text}
🌿 <b>Balcony:</b> {balcony_text}
🚀 <b>מרחב מוגן:</b> {protection_text}

<a href="{url}">View Property</a>

⏰ <i>Found: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"""

        return message

    @staticmethod
    def _has_shelter_text(property_data: Dict) -> bool:
        """Best-effort: detect a building shelter mentioned in the listing's
        tags / description / free text (Yad2 has no dedicated field)."""
        tags = property_data.get('tags') or []
        tag_text = " ".join(
            t.get('name', '') for t in tags if isinstance(t, dict)
        )
        haystack = " ".join([
            str(property_data.get('description') or ''),
            str(property_data.get('search_text') or ''),
            tag_text,
        ])
        return any(sign in haystack for sign in _SHELTER_TEXT_SIGNS)

    @staticmethod
    def should_notify(property_data: Dict) -> bool:
        """False for neighborhoods on the block list — no message is sent."""
        return _norm(property_data.get('neighborhood')) not in BLOCKED_NEIGHBORHOODS

    def notify_new_properties(self, new_properties: List[Dict]) -> int:
        """
        Send notifications for multiple new properties
        
        Args:
            new_properties: List of property dictionaries
            
        Returns:
            int: Number of successfully sent notifications
        """
        if not new_properties:
            return 0
        
        successful_notifications = 0
        
        # Send summary message first
        summary_message = f"🔔 <b>{len(new_properties)} new properties found!</b>"
        if self.send_message(summary_message):
            successful_notifications += 1
        
        # Send individual property notifications
        for property_data in new_properties:
            if not self.should_notify(property_data):
                continue
            message = self.format_property_message(property_data)
            if self.send_message(message):
                successful_notifications += 1
            
            # Small delay between messages to avoid rate limiting
            import time
            time.sleep(1)
        
        return successful_notifications
    
    def send_error_notification(self, error_message: str) -> bool:
        """
        Send error notification
        
        Args:
            error_message: Error description
            
        Returns:
            bool: True if successful, False otherwise
        """
        message = f"⚠️ <b>Yad2 Scraper Error</b>\n\n{error_message}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return self.send_message(message)
    
    def send_scraping_summary(self, total_found: int, new_count: int, search_configs: List[str]) -> bool:
        """
        Send summary of scraping session
        
        Args:
            total_found: Total properties found
            new_count: Number of new properties
            search_configs: List of search configuration names
            
        Returns:
            bool: True if successful, False otherwise
        """
        configs_text = ", ".join(search_configs)
        
        message = f"""📊 <b>Scraping Summary</b>

🔍 <b>Searches:</b> {configs_text}
📋 <b>Total Found:</b> {total_found}
🆕 <b>New Properties:</b> {new_count}

⏰ <i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"""

        return self.send_message(message)