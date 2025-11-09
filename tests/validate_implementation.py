#!/usr/bin/env python3
"""
Quick validation script to verify lifecycle tracking implementation.

This script performs a quick sanity check of the lifecycle tracking functionality
without requiring Google Sheets credentials or actual data scraping.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch

def validate_implementation():
    """Run quick validation checks."""
    print("=" * 60)
    print("LIFECYCLE TRACKING VALIDATION")
    print("=" * 60)

    # Mock the Google Sheets service
    with patch('src.writers.google_sheets_reader_writer.build'):
        with patch('src.writers.google_sheets_reader_writer.Credentials'):
            with patch('src.writers.google_sheets_reader_writer.settings') as mock_settings:
                mock_settings.google_sheets.credentials_file = 'test_creds.json'
                mock_settings.google_sheets.spreadsheet_name = 'Test Sheet'
                mock_settings.google_sheets.worksheet_name = 'Test Worksheet'
                mock_settings.google_sheets.spreadsheet_id = 'test_id'

                from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter

                sheets_handler = GoogleSheetsReaderWriter.__new__(GoogleSheetsReaderWriter)
                sheets_handler.manual_columns = {'decision', 'notes', 'contacted'}
                sheets_handler.lifecycle_columns = {
                    'first_seen_date', 'change_dates', 'change_history',
                    'last_seen_date', 'removed_date'
                }
                sheets_handler.tracked_fields = {
                    'rent', 'city', 'neighborhood', 'street', 'rooms', 'sqm',
                    'floor', 'total_floors', 'elevator', 'parking', 'balcony',
                    'mamad', 'AC', 'renovated', 'furniture', 'pets',
                    'arnona_month', 'vaad', 'entry', 'description'
                }
                sheets_handler.last_update_column = 'last_scraped_at'
                sheets_handler.service = Mock()

    print("\n✅ Module imports successful")

    # Test 1: Change detection
    print("\n1. Testing change detection...")
    old_row = pd.Series({'listing_id': '123', 'rent': 5000, 'rooms': 3})
    new_row = pd.Series({'listing_id': '123', 'rent': 5500, 'rooms': 3})
    changes = sheets_handler._detect_changes(old_row, new_row)

    assert len(changes) == 1, "Should detect exactly one change"
    assert 'rent: 5000→5500' in changes[0], "Should detect rent change"
    print("   ✅ Change detection works correctly")

    # Test 2: New listing initialization
    print("\n2. Testing new listing initialization...")
    existing_df = pd.DataFrame()
    new_df = pd.DataFrame([{'listing_id': '123', 'rent': 5000, 'rooms': 3}])
    current_time = datetime.now().isoformat()

    result = sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', current_time)

    assert len(result) == 1, "Should have one listing"
    assert result.iloc[0]['first_seen_date'] == current_time, "first_seen_date should be set"
    assert result.iloc[0]['last_seen_date'] == current_time, "last_seen_date should be set"
    assert result.iloc[0]['change_dates'] == '', "change_dates should be empty"
    assert result.iloc[0]['removed_date'] == '', "removed_date should be empty"
    print("   ✅ New listing initialization works correctly")

    # Test 3: Change tracking
    print("\n3. Testing change tracking...")
    time1 = '2025-01-09T10:00:00'
    time2 = '2025-01-09T12:00:00'

    existing_df = pd.DataFrame([{
        'listing_id': '123',
        'rent': 5000,
        'first_seen_date': time1,
        'last_seen_date': time1,
        'change_dates': '',
        'change_history': '',
        'removed_date': ''
    }])

    new_df = pd.DataFrame([{'listing_id': '123', 'rent': 5500}])
    result = sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

    assert result.iloc[0]['change_dates'] == time2, "change_dates should be updated"
    assert 'rent: 5000→5500' in result.iloc[0]['change_history'], "change_history should record the change"
    assert result.iloc[0]['first_seen_date'] == time1, "first_seen_date should be preserved"
    print("   ✅ Change tracking works correctly")

    # Test 4: Removal tracking
    print("\n4. Testing removal tracking...")
    existing_df = pd.DataFrame([{
        'listing_id': '123',
        'rent': 5000,
        'first_seen_date': time1,
        'last_seen_date': time1,
        'change_dates': '',
        'change_history': '',
        'removed_date': ''
    }])

    new_df = pd.DataFrame()  # Empty - listing removed
    for col in existing_df.columns:
        new_df[col] = []

    result = sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

    assert result.iloc[0]['removed_date'] == time2, "removed_date should be set"
    print("   ✅ Removal tracking works correctly")

    # Test 5: Manual column preservation
    print("\n5. Testing manual column preservation...")
    existing_df = pd.DataFrame([{
        'listing_id': '123',
        'rent': 5000,
        'decision': 'interested',
        'notes': 'Great location',
        'first_seen_date': time1,
        'last_seen_date': time1,
        'change_dates': '',
        'change_history': '',
        'removed_date': ''
    }])

    new_df = pd.DataFrame([{'listing_id': '123', 'rent': 5500}])
    result = sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

    assert result.iloc[0]['decision'] == 'interested', "decision should be preserved"
    assert result.iloc[0]['notes'] == 'Great location', "notes should be preserved"
    print("   ✅ Manual column preservation works correctly")

    print("\n" + "=" * 60)
    print("✅ ALL VALIDATION CHECKS PASSED")
    print("=" * 60)
    print("\nThe lifecycle tracking implementation is working correctly!")
    print("\nYou can now run the scraper with confidence:")
    print("  python scripts/main.py")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    try:
        validate_implementation()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
