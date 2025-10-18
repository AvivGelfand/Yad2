#!/usr/bin/env python3
"""
Main script to run the Yad2 scraper with Google Sheets integration
"""

import sys
import os
import logging
import argparse
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scrapers.yad2_scraper import Yad2Scraper
from src.writers.google_sheets_writer import GoogleSheetsWriter
from config.settings import settings


def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scraper.log')
        ]
    )


def main():
    parser = argparse.ArgumentParser(description='Yad2 Real Estate Scraper with Google Sheets Integration')
    parser.add_argument('--mode', choices=['basic', 'detailed'], default='detailed',
                       help='Scraping mode: basic (fast) or detailed (comprehensive)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO',
                       help='Logging level')
    parser.add_argument('--max-listings', type=int, default=None,
                       help='Maximum number of listings to process (for testing)')
    parser.add_argument('--backup', action='store_true',
                       help='Create CSV backup after uploading to Google Sheets')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Yad2 scraper...")
    logger.info(f"Mode: {args.mode}")
    
    try:
        # Initialize scraper
        scraper = Yad2Scraper()
        
        # Fetch listings
        logger.info("Fetching listings from Yad2...")
        listings = scraper.fetch_listings()
        
        if not listings:
            logger.warning("No listings found. Exiting.")
            return
        
        # Limit listings if specified
        if args.max_listings:
            listings = listings[:args.max_listings]
            logger.info(f"Limited to {len(listings)} listings for processing")
        
        # Get property data
        if args.mode == 'detailed':
            logger.info("Scraping detailed property information...")
            df = scraper.scrape_detailed_listings(listings)
        else:
            logger.info("Extracting basic property information...")
            df = scraper.get_basic_listings_dataframe(listings)
        
        if df.empty:
            logger.warning("No property data extracted. Exiting.")
            return
        
        logger.info(f"Successfully extracted data for {len(df)} properties")
        
        # Upload to Google Sheets
        logger.info("Writing to Google Sheets...")
        sheets_writer = GoogleSheetsWriter()
        
        # Use upsert to avoid duplicates
        if sheets_writer.upsert_by_id(df, 'listing_id'):
            spreadsheet_url = sheets_writer.get_spreadsheet_url()
            logger.info(f"✅ Successfully updated Google Sheets: {spreadsheet_url}")
            
            # Create backup if requested
            if args.backup:
                sheets_writer.backup_to_csv()
                logger.info("✅ CSV backup created")
        else:
            logger.error("❌ Failed to write to Google Sheets")
            return
        
        # Print summary
        logger.info("="*50)
        logger.info("SCRAPING SUMMARY")
        logger.info("="*50)
        logger.info(f"Total listings processed: {len(df)}")
        logger.info(f"Mode: {args.mode}")
        logger.info(f"Output: Google Sheets")
        
        if not df.empty:
            logger.info(f"Average price: ₪{df['price_ils'].mean():.0f}")
            logger.info(f"Price range: ₪{df['price_ils'].min():.0f} - ₪{df['price_ils'].max():.0f}")
            if 'rooms' in df.columns:
                logger.info(f"Average rooms: {df['rooms'].mean():.1f}")
        
        logger.info("✨ Scraping completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()