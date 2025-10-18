#!/usr/bin/env python3
"""
Debug test script for isolated testing of Yad2 scraper components
"""

import sys
import os
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scrapers.yad2_scraper import Yad2Scraper
from src.writers.google_sheets_writer import GoogleSheetsWriter


def setup_debug_logging():
    """Set up detailed logging for debugging"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )


def test_basic_scraping():
    """Test basic scraping functionality"""
    print("🔍 Testing Basic Scraping")
    print("=" * 30)
    
    try:
        # Initialize scraper with limited search
        scraper = Yad2Scraper()
        
        # Override params for quick test
        scraper.params.update({
            'page': 1,  # Only first page
            'minPrice': '5000',  # Narrow price range for fewer results
            'maxPrice': '8000'
        })
        
        print("Fetching listings...")
        listings = scraper.fetch_listings()
        
        print(f"✅ Found {len(listings)} listings")
        
        if listings:
            # Test basic data extraction
            df = scraper.get_basic_listings_dataframe(listings[:3])  # Only first 3
            print(f"✅ Extracted basic data for {len(df)} properties")
            
            if not df.empty:
                print("\nSample data:")
                print(df[['listing_id', 'price_ils', 'city', 'rooms']].head())
                return df
        
        return None
        
    except Exception as e:
        print(f"❌ Error in basic scraping: {str(e)}")
        raise


def test_detailed_scraping():
    """Test detailed scraping for a single listing"""
    print("\n🔍 Testing Detailed Scraping")
    print("=" * 30)
    
    try:
        scraper = Yad2Scraper()
        scraper.params.update({
            'page': 1,
            'minPrice': '5000',
            'maxPrice': '8000'
        })
        
        print("Fetching listings for detailed test...")
        listings = scraper.fetch_listings()
        
        if listings:
            print(f"Testing detailed scraping on first listing...")
            # Test detailed scraping on just 1 listing
            df = scraper.scrape_detailed_listings(listings[:1])
            
            if not df.empty:
                print(f"✅ Detailed data extracted")
                print(f"Columns: {list(df.columns)}")
                print(f"Sample: {df.iloc[0].to_dict()}")
                return df
        
        return None
        
    except Exception as e:
        print(f"❌ Error in detailed scraping: {str(e)}")
        raise


def test_google_sheets_connection():
    """Test Google Sheets connection without writing data"""
    print("\n📊 Testing Google Sheets Connection")
    print("=" * 35)
    
    try:
        # Check if credentials exist
        if not os.path.exists('config/credentials.json'):
            print("❌ Google Sheets credentials not found.")
            print("Run: python scripts/setup_credentials.py")
            return False
        
        # Test connection
        writer = GoogleSheetsWriter()
        url = writer.get_spreadsheet_url()
        
        if url:
            print(f"✅ Google Sheets connection successful!")
            print(f"Spreadsheet URL: {url}")
            return True
        else:
            print("❌ Could not get spreadsheet URL")
            return False
        
    except Exception as e:
        print(f"❌ Google Sheets connection error: {str(e)}")
        return False


def main():
    """Main debug function"""
    print("🐛 Yad2 Scraper Debug Mode")
    print("=" * 50)
    
    setup_debug_logging()
    
    # Add breakpoint here for debugging
    breakpoint_here = True  # Set breakpoint on this line
    
    try:
        # Test 1: Basic scraping
        df_basic = test_basic_scraping()
        
        # Test 2: Detailed scraping
        df_detailed = test_detailed_scraping()
        
        # Test 3: Google Sheets connection
        sheets_ok = test_google_sheets_connection()
        
        # Summary
        print("\n" + "=" * 50)
        print("🎯 DEBUG SUMMARY")
        print("=" * 50)
        print(f"Basic scraping: {'✅ OK' if df_basic is not None else '❌ Failed'}")
        print(f"Detailed scraping: {'✅ OK' if df_detailed is not None else '❌ Failed'}")
        print(f"Google Sheets: {'✅ OK' if sheets_ok else '❌ Failed'}")
        
        # If we have data and Google Sheets works, offer to test upload
        if df_basic is not None and sheets_ok:
            response = input("\n🤔 Want to test uploading sample data to Google Sheets? (y/N): ")
            if response.lower() == 'y':
                try:
                    writer = GoogleSheetsWriter()
                    success = writer.write(df_basic)  # Use basic data for test
                    if success:
                        print("✅ Test upload successful!")
                        print(f"🔗 Check your sheet: {writer.get_spreadsheet_url()}")
                    else:
                        print("❌ Test upload failed")
                except Exception as e:
                    print(f"❌ Upload error: {str(e)}")
        
        print("\n✨ Debug session completed!")
        
    except KeyboardInterrupt:
        print("\n🛑 Debug session interrupted")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()