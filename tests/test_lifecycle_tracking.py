"""
Unit tests for lifecycle tracking functionality in GoogleSheetsReaderWriter.

Tests cover:
- Change detection logic
- First appearance tracking
- Change history tracking
- Removal tracking
- Edge cases (reappearing listings, empty data, etc.)
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter


class TestLifecycleTracking(unittest.TestCase):
    """Test lifecycle tracking functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the Google Sheets service authentication
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

    def test_detect_changes_with_no_changes(self):
        """Test that no changes are detected when data is identical."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv'
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0, "No changes should be detected for identical data")

    def test_detect_changes_with_single_change(self):
        """Test detection of a single field change."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5500,
            'rooms': 3,
            'city': 'Tel Aviv'
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 1, "Should detect exactly one change")
        self.assertIn('rent: 5000→5500', changes[0], "Should track rent change correctly")

    def test_detect_changes_with_multiple_changes(self):
        """Test detection of multiple field changes."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv',
            'elevator': True
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5500,
            'rooms': 4,
            'city': 'Tel Aviv',
            'elevator': False
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 3, "Should detect three changes")

        # Verify all changes are tracked
        changes_str = ', '.join(changes)
        self.assertIn('rent', changes_str)
        self.assertIn('rooms', changes_str)
        self.assertIn('elevator', changes_str)

    def test_detect_changes_with_empty_values(self):
        """Test change detection with empty/None values."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'description': None
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'description': 'Nice apartment'
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 1, "Should detect description change from None")
        self.assertIn('description: empty→Nice apartment', changes[0])

    def test_detect_changes_ignores_untracked_fields(self):
        """Test that changes in untracked fields are ignored."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'created_at': '2025-01-01',
            'search_timestamp': '2025-01-01'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'created_at': '2025-01-02',  # Changed but not tracked
            'search_timestamp': '2025-01-02'  # Changed but not tracked
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0, "Should ignore changes in untracked fields")

    def test_merge_new_listing_initializes_lifecycle(self):
        """Test that new listings get proper lifecycle initialization."""
        existing_df = pd.DataFrame()
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv'
        }])

        current_time = '2025-01-09T10:00:00'
        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', current_time)

        # Verify lifecycle columns are initialized
        self.assertEqual(merged_df.iloc[0]['first_seen_date'], current_time)
        self.assertEqual(merged_df.iloc[0]['last_seen_date'], current_time)
        self.assertEqual(merged_df.iloc[0]['change_dates'], '')
        self.assertEqual(merged_df.iloc[0]['change_history'], '')
        self.assertEqual(merged_df.iloc[0]['removed_date'], '')

    def test_merge_preserves_first_seen_date(self):
        """Test that first_seen_date is preserved on updates."""
        first_time = '2025-01-09T10:00:00'
        second_time = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'first_seen_date': first_time,
            'last_seen_date': first_time,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', second_time)

        # Verify first_seen_date is preserved
        self.assertEqual(merged_df.iloc[0]['first_seen_date'], first_time)
        self.assertEqual(merged_df.iloc[0]['last_seen_date'], second_time)

    def test_merge_tracks_changes_with_history(self):
        """Test that changes are properly tracked with history."""
        first_time = '2025-01-09T10:00:00'
        second_time = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'first_seen_date': first_time,
            'last_seen_date': first_time,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500,  # Changed
            'rooms': 3
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', second_time)

        # Verify change tracking
        self.assertEqual(merged_df.iloc[0]['change_dates'], second_time)
        self.assertIn('rent: 5000→5500', merged_df.iloc[0]['change_history'])
        self.assertIn(second_time, merged_df.iloc[0]['change_history'])

    def test_merge_accumulates_multiple_changes(self):
        """Test that multiple changes over time are accumulated."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'
        time3 = '2025-01-09T14:00:00'

        # Initial state
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

        # First change
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500,
            'rooms': 3
        }])
        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

        # Second change
        existing_df = merged_df.copy()
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500,
            'rooms': 4  # Different change
        }])
        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time3)

        # Verify both changes are tracked
        self.assertIn(time2, merged_df.iloc[0]['change_dates'])
        self.assertIn(time3, merged_df.iloc[0]['change_dates'])
        self.assertIn('rent: 5000→5500', merged_df.iloc[0]['change_history'])
        self.assertIn('rooms: 3→4', merged_df.iloc[0]['change_history'])

    def test_merge_sets_removed_date_for_missing_listings(self):
        """Test that removed_date is set when a listing disappears."""
        first_time = '2025-01-09T10:00:00'
        second_time = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([
            {
                'listing_id': '123',
                'rent': 5000,
                'first_seen_date': first_time,
                'last_seen_date': first_time,
                'change_dates': '',
                'change_history': '',
                'removed_date': ''
            },
            {
                'listing_id': '456',
                'rent': 6000,
                'first_seen_date': first_time,
                'last_seen_date': first_time,
                'change_dates': '',
                'change_history': '',
                'removed_date': ''
            }
        ])

        # Only listing 123 is in new scrape
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', second_time)

        # Verify listing 456 has removed_date set
        listing_456 = merged_df[merged_df['listing_id'] == '456'].iloc[0]
        self.assertEqual(listing_456['removed_date'], second_time)

        # Verify listing 123 does not have removed_date
        listing_123 = merged_df[merged_df['listing_id'] == '123'].iloc[0]
        self.assertEqual(listing_123['removed_date'], '')

    def test_merge_clears_removed_date_when_listing_reappears(self):
        """Test that removed_date is cleared when a listing reappears."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'
        time3 = '2025-01-09T14:00:00'

        # Listing was removed
        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'first_seen_date': time1,
            'last_seen_date': time1,
            'change_dates': '',
            'change_history': '',
            'removed_date': time2  # Was removed
        }])

        # Listing reappears
        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time3)

        # Verify removed_date is cleared
        self.assertEqual(merged_df.iloc[0]['removed_date'], '')
        self.assertEqual(merged_df.iloc[0]['last_seen_date'], time3)

    def test_merge_preserves_manual_columns(self):
        """Test that manual columns are never overwritten."""
        first_time = '2025-01-09T10:00:00'
        second_time = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'decision': 'interested',
            'notes': 'Great location',
            'contacted': 'yes',
            'first_seen_date': first_time,
            'last_seen_date': first_time,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500,
            'decision': '',  # Should be ignored
            'notes': '',  # Should be ignored
            'contacted': ''  # Should be ignored
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', second_time)

        # Verify manual columns are preserved
        self.assertEqual(merged_df.iloc[0]['decision'], 'interested')
        self.assertEqual(merged_df.iloc[0]['notes'], 'Great location')
        self.assertEqual(merged_df.iloc[0]['contacted'], 'yes')

        # Verify rent was updated
        self.assertEqual(merged_df.iloc[0]['rent'], 5500)

    def test_merge_handles_empty_existing_dataframe(self):
        """Test merging with empty existing dataframe (first run)."""
        existing_df = pd.DataFrame()
        new_df = pd.DataFrame([
            {'listing_id': '123', 'rent': 5000},
            {'listing_id': '456', 'rent': 6000}
        ])

        current_time = '2025-01-09T10:00:00'
        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', current_time)

        # Verify both listings are added with lifecycle tracking
        self.assertEqual(len(merged_df), 2)
        for _, row in merged_df.iterrows():
            self.assertEqual(row['first_seen_date'], current_time)
            self.assertEqual(row['last_seen_date'], current_time)
            self.assertEqual(row['change_dates'], '')

    def test_merge_handles_empty_new_dataframe(self):
        """Test merging with empty new dataframe (all listings removed)."""
        first_time = '2025-01-09T10:00:00'
        second_time = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([
            {
                'listing_id': '123',
                'rent': 5000,
                'first_seen_date': first_time,
                'last_seen_date': first_time,
                'change_dates': '',
                'change_history': '',
                'removed_date': ''
            }
        ])

        new_df = pd.DataFrame()

        # Add required columns to new_df to match structure
        for col in existing_df.columns:
            if col not in new_df.columns:
                new_df[col] = []

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', second_time)

        # Verify listing has removed_date set
        self.assertEqual(merged_df.iloc[0]['removed_date'], second_time)

    def test_change_history_format(self):
        """Test that change history maintains proper format."""
        time1 = '2025-01-09T10:00:00'
        time2 = '2025-01-09T12:00:00'

        existing_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3,
            'city': 'Tel Aviv',
            'first_seen_date': time1,
            'last_seen_date': time1,
            'change_dates': '',
            'change_history': '',
            'removed_date': ''
        }])

        new_df = pd.DataFrame([{
            'listing_id': '123',
            'rent': 5500,
            'rooms': 4,
            'city': 'Tel Aviv'
        }])

        merged_df = self.sheets_handler._merge_dataframes(existing_df, new_df, 'listing_id', time2)

        change_history = merged_df.iloc[0]['change_history']

        # Verify format: [timestamp] field: old→new, field: old→new
        self.assertTrue(change_history.startswith(f'[{time2}]'))
        self.assertIn('→', change_history)
        self.assertIn(',', change_history)  # Multiple changes separated by comma


class TestChangeDetectionEdgeCases(unittest.TestCase):
    """Test edge cases in change detection."""

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

    def test_detect_changes_with_nan_values(self):
        """Test change detection with NaN values."""
        import numpy as np

        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'description': np.nan
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'description': np.nan
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0, "Should not detect changes for matching NaN values")

    def test_detect_changes_from_value_to_empty(self):
        """Test change detection when value becomes empty."""
        old_row = pd.Series({
            'listing_id': '123',
            'description': 'Nice apartment'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'description': ''
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 1)
        self.assertIn('Nice apartment→empty', changes[0])

    def test_detect_changes_with_boolean_values(self):
        """Test change detection with boolean values."""
        old_row = pd.Series({
            'listing_id': '123',
            'elevator': True,
            'parking': False
        })
        new_row = pd.Series({
            'listing_id': '123',
            'elevator': False,
            'parking': True
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 2)

        changes_str = ', '.join(changes)
        self.assertIn('elevator', changes_str)
        self.assertIn('parking', changes_str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
