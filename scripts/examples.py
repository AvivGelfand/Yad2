#!/usr/bin/env python3
"""
Example script demonstrating how to use the Yad2 scraper components
"""

import sys
import os
import pandas as pd

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scrapers.yad2_scraper import Yad2Scraper
from src.writers.google_sheets_writer import GoogleSheetsWriter



def example_google_sheets():
    """Example: Google Sheets integration (requires setup)"""
    print("\n📊 Example: Google Sheets Integration")
    print("=" * 35)
    
    try:
        # Check if credentials exist
        if not os.path.exists('config/credentials.json'):
            print("❌ Google Sheets credentials not found.")
            print("Run: python scripts/setup_credentials.py")
            return
        
        # Initialize components
        scraper = Yad2Scraper()
        sheets_writer = GoogleSheetsWriter()
        
        # Get sample data
        scraper.params['page'] = 1
        listings = scraper.fetch_listings()
        
        if listings:
            df = scraper.get_basic_listings_dataframe(listings[:3])
            
            if not df.empty:
                # Upload to Google Sheets
                print("Uploading to Google Sheets...")
                success = sheets_writer.write(df)
                
                if success:
                    url = sheets_writer.get_spreadsheet_url()
                    print(f"✅ Successfully uploaded to Google Sheets!")
                    print(f"🔗 URL: {url}")
                else:
                    print("❌ Failed to upload to Google Sheets")
        
    except Exception as e:
        print(f"❌ Google Sheets error: {str(e)}")
        print("Make sure you've set up the credentials properly.")


def example_custom_search():
    """Example: Custom search parameters"""
    print("\n🎯 Example: Custom Search Parameters")
    print("=" * 35)
    
    # Custom search parameters
    custom_params = {
        "minPrice": "2000",
        "maxPrice": "5000", 
        "minRooms": "2",
        "maxRooms": "3",
        "city": "6600",  # Different city code
        "elevator": "1",
        "balcony": "1"
    }
    
    scraper = Yad2Scraper(params=custom_params)
    scraper.params['page'] = 1  # First page only
    
    listings = scraper.fetch_listings()
    
    if listings:
        df = scraper.get_basic_listings_dataframe(listings[:5])
        print(f"Found {len(df)} properties with custom search")
        
        if not df.empty:
            print(f"Price range: ₪{df['price_ils'].min()} - ₪{df['price_ils'].max()}")
            print(f"Average price: ₪{df['price_ils'].mean():.0f}")
    else:
        print("No listings found with custom parameters")


def main():
    print("🚀 Yad2 Scraper Examples")
    print("=" * 50)
    
    # Run examples
    example_custom_search()
    example_google_sheets()
    
    print("\n" + "=" * 50)
    print("✨ Examples completed!")
    print("\nNext steps:")
    print("1. Run: python scripts/run_scraper.py")
    print("2. Set up Google Sheets: python scripts/setup_credentials.py")
    print("3. Customize search parameters in config/settings.py")


if __name__ == "__main__":
    main()