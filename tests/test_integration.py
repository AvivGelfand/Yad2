"""
Integration tests for the complete lifecycle tracking workflow.

Tests the full end-to-end flow of scraping, updating Google Sheets,
and tracking lifecycle events across multiple scrape cycles.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter


class TestIntegrationWorkflow(unittest.TestCase):
    """Test complete workflow scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('src.writers.google_sheets_reader_writer.build'):
            with patch('src.writers.google_sheets_reader_writer.Credentials'):
                with patch('src.writers.google_sheets_reader_writer.settings') as mock_settings:
                    mock_settings.google_sheets.credentials_file = 'test_creds.json'
                    mock_settings.google_sheets.spreadsheet_name = 'Test Sheet'
                    mock_settings.google_sheets.worksheet_name = 'Test Worksheet'
                    mock_settings.google_sheets.spreadsheet_id = 'test_id'

                    self.sheets_handler = GoogleSheetsReaderWriter.__new__(GoogleSheetsReaderWriter)
                    self.sheets_handler.manual_columns = {'decision', 'notes', 'contacted'}
                    self.sheets_handler.lifecycle_columns = {
                        'first_seen_date', 'change_dates', 'change_history',
                        'last_seen_date', 'removed_date'
                    }
                    self.sheets_handler.tracked_fields = {
                        'rent', 'city', 'neighborhood', 'street', 'rooms', 'sqm',
                        'floor', 'total_floors', 'elevator', 'parking', 'balcony',
                        'mamad', 'AC', 'renovated', 'furniture', 'pets',
                        'arnona_month', 'vaad', 'entry', 'description'
                    }
                    self.sheets_handler.last_update_column = 'last_scraped_at'
                    self.sheets_handler.service = Mock()

    def test_complete_lifecycle_scenario(self):
        """
        Test a complete lifecycle scenario:
        1. First scrape - new listings appear
        2. Second scrape - one listing changes, one remains, one is removed
        3. Third scrape - removed listing reappears
        """
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'
        time3 = '2025-01-09T14:00:00'

        # SCRAPE 1: Three new listings appear
        existing_df = pd.DataFrame()
        new_df = pd.DataFrame([
            {'listing_id': '123', 'rent': 5000, 'rooms': 3, 'city': 'Tel Aviv'},
            {'listing_id': '456', 'rent': 6000, 'rooms': 4, 'city': 'Tel Aviv'},
            {'listing_id': '789', 'rent': 7000, 'rooms': 3, 'city': 'Tel Aviv'}
        ])

        result1 = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time1)

        # Verify all three listings have proper lifecycle initialization
        self.assertEqual(len(result1), 3)
        for _, row in result1.iterrows():
            self.assertEqual(row['first_seen_date'], time1)
            self.assertEqual(row['last_seen_date'], time1)
            self.assertEqual(row['change_dates'], '')
            self.assertEqual(row['removed_date'], '')

        # SCRAPE 2: One changes, one removed, one unchanged
        existing_df = result1.copy()
        new_df = pd.DataFrame([
            {'listing_id': '123', 'rent': 5500, 'rooms': 3, 'city': 'Tel Aviv'},  # Changed rent
            {'listing_id': '456', 'rent': 6000, 'rooms': 4, 'city': 'Tel Aviv'}   # Unchanged
            # '789' is missing - should be marked as removed
        ])

        result2 = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

        # Verify listing 123 has change tracked
        listing_123 = result2[result2['listing_id'] == '123'].iloc[0]
        self.assertEqual(listing_123['first_seen_date'], time1)
        self.assertEqual(listing_123['last_seen_date'], time2)
        self.assertEqual(listing_123['change_dates'], time2)
        self.assertIn('rent: 5000→5500', listing_123['change_history'])

        # Verify listing 456 is unchanged
        listing_456 = result2[result2['listing_id'] == '456'].iloc[0]
        self.assertEqual(listing_456['first_seen_date'], time1)
        self.assertEqual(listing_456['last_seen_date'], time2)
        self.assertEqual(listing_456['change_dates'], '')

        # Verify listing 789 is marked as removed
        listing_789 = result2[result2['listing_id'] == '789'].iloc[0]
        self.assertEqual(listing_789['removed_date'], time2)

        # SCRAPE 3: Removed listing reappears with changes
        existing_df = result2.copy()
        new_df = pd.DataFrame([
            {'listing_id': '123', 'rent': 5500, 'rooms': 3, 'city': 'Tel Aviv'},
            {'listing_id': '456', 'rent': 6000, 'rooms': 4, 'city': 'Tel Aviv'},
            {'listing_id': '789', 'rent': 7500, 'rooms': 3, 'city': 'Tel Aviv'}  # Reappeared with price change
        ])

        result3 = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time3)

        # Verify listing 789 has removed_date cleared and change tracked
        listing_789 = result3[result3['listing_id'] == '789'].iloc[0]
        self.assertEqual(listing_789['removed_date'], '')
        self.assertEqual(listing_789['last_seen_date'], time3)
        self.assertIn('rent: 7000→7500', listing_789['change_history'])
        self.assertEqual(listing_789['first_seen_date'], time1)  # Original first_seen preserved

    def test_manual_columns_preserved_through_lifecycle(self):
        """Test that manual columns are preserved through all lifecycle events."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'
        time3 = '2025-01-09T14:00:00'

        # Initial scrape with manual data
        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'decision': 'interested',
            'notes': 'Great location',
            'contacted': 'yes',
            'first_seen_date': time1,
            'last_seen_date': time1,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        # Update with changes
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500  # Changed
        }])

        result1 = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

        # Verify manual columns preserved
        self.assertEqual(result1.iloc[0]['decision'], 'interested')
        self.assertEqual(result1.iloc[0]['notes'], 'Great location')
        self.assertEqual(result1.iloc[0]['contacted'], 'yes')

        # Remove listing
        new_df = pd.DataFrame()
        for col in existing_df.columns:
            new_df[col] = []

        result2 = self.sheets_handler._merge_dataframes(result1, new_df, 'listing_id', time3)

        # Verify manual columns still preserved even when removed
        self.assertEqual(result2.iloc[0]['decision'], 'interested')
        self.assertEqual(result2.iloc[0]['notes'], 'Great location')
        self.assertEqual(result2.iloc[0]['contacted'], 'yes')
        self.assertEqual(result2.iloc[0]['removed_date'], time3)

    def test_multiple_properties_with_different_lifecycles(self):
        """Test handling multiple properties with different lifecycle states."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([
            {
                'listing_id': '111',
                'rent': 4000,
                'first_seen_date': time1,
                'last_seen_date': time1,
                'change_dates': '',
                'change_history': '',
                'removed_date': ''
            },
            {
                'listing_id': '222',
                'rent': 5000,
                'first_seen_date': time1,
                'last_seen_date': time1,
                'change_dates': '',
                'change_history': '',
                'removed_date': ''
            }
        ])

        new_df = pd.DataFrame([
            {'listing_id': '111', 'rent': 4500},  # Changed
            {'listing_id': '333', 'rent': 6000}   # New
            # 222 removed
        ])

        result = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

        self.assertEqual(len(result), 3)

        # Check changed listing
        listing_111 = result[result['listing_id'] == '111'].iloc[0]
        self.assertIn('rent: 4000→4500', listing_111['change_history'])

        # Check removed listing
        listing_222 = result[result['listing_id'] == '222'].iloc[0]
        self.assertEqual(listing_222['removed_date'], time2)

        # Check new listing
        listing_333 = result[result['listing_id'] == '333'].iloc[0]
        self.assertEqual(listing_333['first_seen_date'], time2)

    def test_no_false_changes_when_identical(self):
        """Test that identical data doesn't create false change records."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'
        time3 = '2025-01-09T14:00:00'

        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'first_seen_date': time1,
            'last_seen_date': time1,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        # Multiple scrapes with identical data
        for scrape_time in [time2, time3]:
            new_df = pd.DataFrame([{
                'listing_id': '123',
                'rent': 5000,
                'rooms': 3
            }])

            existing_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', scrape_time)

        # Verify no changes were recorded
        self.assertEqual(existing_df.iloc[0]['change_dates'], '')
        self.assertEqual(existing_df.iloc[0]['change_history'], '')
        self.assertEqual(existing_df.iloc[0]['last_seen_date'], time3)

    def test_column_order_preserved(self):
        """Test that column order is preserved through merges."""
        time1 = '2025-01-09T10:00:00'

        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'city': 'Tel Aviv',
            'rooms': 3
        }])

        # Get initial column order (before lifecycle columns)
        initial_cols = list(new_df.columns)

        result = self.sheets_handler._merge_dataframes(pd.DataFrame(), new_df, 'listing_id', time1)

        # Verify original columns come first, then lifecycle columns
        result_cols = list(result.columns)
        for i, col in enumerate(initial_cols):
            self.assertEqual(result_cols[i], col)


if __name__ == '__main__':
    unittest.main(verbosity=2)
