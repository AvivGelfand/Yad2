"""
Tests for value normalization to prevent false change detection.

Tests the _normalize_value method that handles format mismatches like:
- TRUE/FALSE strings vs True/False booleans
- int vs float (1 vs 1.0)
- String vs numeric types
"""

import unittest
from unittest.mock import Mock, patch
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter


class TestValueNormalization(unittest.TestCase):
    """Test value normalization to prevent false positives."""

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

    def test_normalize_boolean_string_true(self):
        """Test that 'TRUE' string normalizes to Python True."""
        self.assertEqual(self.sheets_handler._normalize_value('TRUE'), True)
        self.assertEqual(self.sheets_handler._normalize_value('True'), True)
        self.assertEqual(self.sheets_handler._normalize_value('true'), True)

    def test_normalize_boolean_string_false(self):
        """Test that 'FALSE' string normalizes to Python False."""
        self.assertEqual(self.sheets_handler._normalize_value('FALSE'), False)
        self.assertEqual(self.sheets_handler._normalize_value('False'), False)
        self.assertEqual(self.sheets_handler._normalize_value('false'), False)

    def test_normalize_boolean_native(self):
        """Test that Python booleans remain unchanged."""
        self.assertEqual(self.sheets_handler._normalize_value(True), True)
        self.assertEqual(self.sheets_handler._normalize_value(False), False)

    def test_normalize_int_to_int(self):
        """Test that integers remain as integers."""
        self.assertEqual(self.sheets_handler._normalize_value(5), 5)
        self.assertEqual(self.sheets_handler._normalize_value(0), 0)
        self.assertEqual(self.sheets_handler._normalize_value(-10), -10)

    def test_normalize_float_whole_number_to_int(self):
        """Test that float whole numbers (1.0) normalize to int (1)."""
        self.assertEqual(self.sheets_handler._normalize_value(1.0), 1)
        self.assertEqual(self.sheets_handler._normalize_value(150.0), 150)
        self.assertEqual(self.sheets_handler._normalize_value(0.0), 0)

    def test_normalize_float_decimal_remains_float(self):
        """Test that floats with decimals remain as floats."""
        self.assertEqual(self.sheets_handler._normalize_value(3.5), 3.5)
        self.assertEqual(self.sheets_handler._normalize_value(150.5), 150.5)
        self.assertEqual(self.sheets_handler._normalize_value(1.1), 1.1)

    def test_normalize_none_values(self):
        """Test that None/NaN/empty normalize to None."""
        self.assertIsNone(self.sheets_handler._normalize_value(None))
        self.assertIsNone(self.sheets_handler._normalize_value(''))
        self.assertIsNone(self.sheets_handler._normalize_value(pd.NA))
        self.assertIsNone(self.sheets_handler._normalize_value(float('nan')))

    def test_normalize_string_strips_whitespace(self):
        """Test that strings are stripped of whitespace."""
        self.assertEqual(self.sheets_handler._normalize_value('  hello  '), 'hello')
        self.assertEqual(self.sheets_handler._normalize_value('\tTel Aviv\n'), 'Tel Aviv')

    def test_no_false_changes_boolean_format_mismatch(self):
        """Test that TRUE/FALSE vs True/False doesn't trigger changes."""
        old_row = pd.Series({
            'listing_id': '123',
            'elevator': 'TRUE',  # String from Google Sheets
            'parking': 'FALSE',
            'balcony': 'TRUE'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'elevator': True,    # Python bool from scraper
            'parking': False,
            'balcony': True
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0, "No changes should be detected for boolean format mismatches")

    def test_no_false_changes_int_float_mismatch(self):
        """Test that 1 vs 1.0 doesn't trigger changes."""
        old_row = pd.Series({
            'listing_id': '123',
            'floor': 1,           # int
            'total_floors': 1,    # int
            'arnona_month': 150   # int
        })
        new_row = pd.Series({
            'listing_id': '123',
            'floor': 1.0,         # float from Google Sheets
            'total_floors': 1.0,  # float
            'arnona_month': 150.0 # float
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0, "No changes should be detected for int/float mismatches")

    def test_no_false_changes_identical_values(self):
        """Test the exact scenario from the user's example."""
        old_row = pd.Series({
            'listing_id': '123',
            'mamad': 'FALSE',
            'sqm': 80,
            'floor': 1,
            'AC': 'TRUE',
            'parking': 'TRUE',
            'rent': 5900,
            'rooms': 3.5,
            'arnona_month': 150,
            'pets': 'TRUE',
            'total_floors': 1,
            'balcony': 'TRUE',
            'elevator': 'TRUE'
        })
        new_row = pd.Series({
            'listing_id': '123',
            'mamad': False,
            'sqm': 80,
            'floor': 1,
            'AC': True,
            'parking': True,
            'rent': 5900,
            'rooms': 3.5,
            'arnona_month': 150.0,
            'pets': True,
            'total_floors': 1.0,
            'balcony': True,
            'elevator': True
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 0,
            f"No changes should be detected. Found: {changes}")

    def test_real_change_still_detected(self):
        """Test that actual changes are still detected after normalization."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5900,
            'elevator': 'TRUE',
            'floor': 1
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 6000,      # Real change
            'elevator': True,  # Format difference (not a change)
            'floor': 2         # Real change
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 2, "Should detect 2 real changes")

        changes_str = ', '.join(changes)
        self.assertIn('rent', changes_str)
        self.assertIn('5900→6000', changes_str)
        self.assertIn('floor', changes_str)
        self.assertIn('1→2', changes_str)
        self.assertNotIn('elevator', changes_str)

    def test_mixed_types_with_real_changes(self):
        """Test normalization with mix of real and format-only differences."""
        old_row = pd.Series({
            'listing_id': '123',
            'rent': 5000,
            'rooms': 3.5,
            'elevator': 'TRUE',
            'floor': 1,
            'arnona_month': 150
        })
        new_row = pd.Series({
            'listing_id': '123',
            'rent': 5500,      # Real change
            'rooms': 3.5,      # Same
            'elevator': True,  # Format only
            'floor': 1.0,      # Format only
            'arnona_month': 150.0  # Format only
        })

        changes = self.sheets_handler._detect_changes(old_row, new_row)
        self.assertEqual(len(changes), 1, "Should detect only 1 real change")
        self.assertIn('rent: 5000→5500', changes[0])


class TestNormalizationEdgeCases(unittest.TestCase):
    """Test edge cases in normalization."""

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
                    self.sheets_handler.tracked_fields = {
                        'rent', 'city', 'elevator', 'floor', 'description'
                    }

    def test_normalize_zero_values(self):
        """Test that zero is handled correctly."""
        self.assertEqual(self.sheets_handler._normalize_value(0), 0)
        self.assertEqual(self.sheets_handler._normalize_value(0.0), 0)
        self.assertEqual(self.sheets_handler._normalize_value('0'), '0')

    def test_normalize_negative_numbers(self):
        """Test negative number normalization."""
        self.assertEqual(self.sheets_handler._normalize_value(-1), -1)
        self.assertEqual(self.sheets_handler._normalize_value(-1.0), -1)
        self.assertEqual(self.sheets_handler._normalize_value(-3.5), -3.5)

    def test_normalize_large_numbers(self):
        """Test large number normalization."""
        self.assertEqual(self.sheets_handler._normalize_value(1000000), 1000000)
        self.assertEqual(self.sheets_handler._normalize_value(1000000.0), 1000000)

    def test_string_not_boolean(self):
        """Test that non-boolean strings remain as strings."""
        self.assertEqual(self.sheets_handler._normalize_value('TRUEX'), 'TRUEX')
        self.assertEqual(self.sheets_handler._normalize_value('FALSEE'), 'FALSEE')
        self.assertEqual(self.sheets_handler._normalize_value('Yes'), 'Yes')
        self.assertEqual(self.sheets_handler._normalize_value('No'), 'No')


if __name__ == '__main__':
    unittest.main(verbosity=2)
