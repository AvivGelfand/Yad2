import time
import sys
import os
# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from notifications.telegram_notifier import TelegramNotifier
from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter
from config.settings import settings
from config.search_configs import SEARCH_CONFIGURATIONS

from scripts.scraper import Yad2MultiSearchScraper

if __name__ == "__main__":
    # Use the multi-search scraper instead of single scraper
    scraper = Yad2MultiSearchScraper(SEARCH_CONFIGURATIONS,enable_notifications=True)

    # Run multi-search and get combined dataframe
    df = scraper.run_multi_search()

    if df.empty:
        print("No listings found across all searches")
        exit(1)

    # Initialize sheets handler
    sheets_handler = GoogleSheetsReaderWriter()

    # Create backup before updating
    # backup_name = sheets_handler.backup_sheet()

    # Perform incremental update (preserves manual columns)
    update_stats = sheets_handler.upsert_listings(df, 'listing_id')

    # Note: Notifications are handled by the scraper's notification system
    # No need to send duplicate notifications here

    # Get summary including manual column usage
    summary = sheets_handler.get_update_summary()
    manual_summary = sheets_handler.get_manual_columns_summary()

    print(f"✅ Update complete!")
    print(f"New listings: {update_stats['new']}")
    print(f"Updated listings: {update_stats['updated']}")
    print(f"Total listings: {summary['total_listings']}")
