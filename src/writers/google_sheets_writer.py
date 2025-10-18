import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import time

from .base_writer import BaseWriter
from config.settings import settings


class GoogleSheetsWriter(BaseWriter):
    """Writer class for Google Sheets integration"""
    
    def __init__(self, credentials_file: Optional[str] = None, 
                 spreadsheet_name: Optional[str] = None,
                 worksheet_name: Optional[str] = None):
        """
        Initialize GoogleSheetsWriter
        
        Args:
            credentials_file: Path to Google service account credentials JSON file
            spreadsheet_name: Name of the Google Spreadsheet
            worksheet_name: Name of the worksheet within the spreadsheet
        """
        self.credentials_file = credentials_file or settings.google_sheets.credentials_file
        self.spreadsheet_name = spreadsheet_name or settings.google_sheets.spreadsheet_name
        self.worksheet_name = worksheet_name or settings.google_sheets.worksheet_name
        
        self.logger = logging.getLogger(__name__)
        self._client = None
        self._spreadsheet = None
        self._worksheet = None
        
        # Initialize connection
        self._connect()
    
    def _connect(self):
        """Establish connection to Google Sheets"""
        try:
            # Define the scope for Google Sheets and Google Drive APIs
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Load credentials
            credentials = Credentials.from_service_account_file(
                self.credentials_file, scopes=scope
            )
            
            # Create the client
            self._client = gspread.authorize(credentials)
            self.logger.info("Successfully connected to Google Sheets API")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Google Sheets: {str(e)}")
            raise
    
    def _get_or_create_spreadsheet(self) -> gspread.Spreadsheet:
        """Get existing spreadsheet or create a new one"""
        try:
            # Try to open existing spreadsheet
            spreadsheet = self._client.open(self.spreadsheet_name)
            self.logger.info(f"Opened existing spreadsheet: {self.spreadsheet_name}")
            return spreadsheet
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet
            spreadsheet = self._client.create(self.spreadsheet_name)
            self.logger.info(f"Created new spreadsheet: {self.spreadsheet_name}")
            
            # Share with user email if provided
            if settings.google_sheets.share_with_email:
                spreadsheet.share(
                    settings.google_sheets.share_with_email, 
                    perm_type='user', 
                    role='writer'
                )
                self.logger.info(f"Shared spreadsheet with {settings.google_sheets.share_with_email}")
            
            return spreadsheet
    
    def _get_or_create_worksheet(self) -> gspread.Worksheet:
        """Get existing worksheet or create a new one"""
        if not self._spreadsheet:
            self._spreadsheet = self._get_or_create_spreadsheet()
        
        try:
            # Try to get existing worksheet
            worksheet = self._spreadsheet.worksheet(self.worksheet_name)
            self.logger.info(f"Found existing worksheet: {self.worksheet_name}")
            return worksheet
        except gspread.WorksheetNotFound:
            # Create new worksheet
            worksheet = self._spreadsheet.add_worksheet(
                title=self.worksheet_name, 
                rows=1000, 
                cols=20
            )
            self.logger.info(f"Created new worksheet: {self.worksheet_name}")
            return worksheet
    
    def write(self, data: pd.DataFrame) -> bool:
        """
        Write DataFrame to Google Sheets (overwrites existing data)
        
        Args:
            data: pandas DataFrame to write
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if data.empty:
                self.logger.warning("No data to write")
                return True
            
            worksheet = self._get_or_create_worksheet()
            
            # Clear existing data
            worksheet.clear()
            
            # Add timestamp column
            data_with_timestamp = data.copy()
            data_with_timestamp['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Convert DataFrame to list of lists for Google Sheets
            values = [data_with_timestamp.columns.tolist()] + data_with_timestamp.values.tolist()
            
            # Write data to sheet
            worksheet.update(values,
                            #   value_input_option='USER_ENTERED'
                              )
            
            # Format header row
            self._format_header_row(worksheet)
            
            self.logger.info(f"Successfully wrote {len(data)} rows to Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write to Google Sheets: {str(e)}")
            return False
    
    def update(self, data: pd.DataFrame) -> bool:
        """
        Update existing data in Google Sheets (append new rows)
        
        Args:
            data: pandas DataFrame to append
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if data.empty:
                self.logger.warning("No data to update")
                return True
            
            worksheet = self._get_or_create_worksheet()
            
            # Check if sheet is empty
            try:
                existing_data = worksheet.get_all_records()
                if not existing_data:
                    # If empty, write headers first
                    return self.write(data)
            except Exception:
                # If error reading, assume empty and write with headers
                return self.write(data)
            
            # Add timestamp column
            data_with_timestamp = data.copy()
            data_with_timestamp['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Convert to list of lists (without headers)
            values = data_with_timestamp.values.tolist()
            
            # Append data
            worksheet.append_rows(values, value_input_option='USER_ENTERED')
            
            self.logger.info(f"Successfully appended {len(data)} rows to Google Sheets")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update Google Sheets: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """
        Clear all data from the worksheet
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            worksheet = self._get_or_create_worksheet()
            worksheet.clear()
            self.logger.info("Successfully cleared Google Sheets data")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear Google Sheets: {str(e)}")
            return False
    
    def upsert_by_id(self, data: pd.DataFrame, id_column: str = 'listing_id') -> bool:
        """
        Update existing rows or insert new ones based on ID column
        
        Args:
            data: pandas DataFrame to upsert
            id_column: Column name to use as unique identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if data.empty:
                self.logger.warning("No data to upsert")
                return True
            
            worksheet = self._get_or_create_worksheet()
            
            # Get existing data
            try:
                existing_data = pd.DataFrame(worksheet.get_all_records())
                if existing_data.empty:
                    return self.write(data)
            except Exception:
                return self.write(data)
            
            # Add timestamp
            data_with_timestamp = data.copy()
            data_with_timestamp['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Perform upsert logic
            if id_column in existing_data.columns and id_column in data_with_timestamp.columns:
                # Update existing records
                updated_data = existing_data.copy()
                for _, new_row in data_with_timestamp.iterrows():
                    mask = updated_data[id_column] == new_row[id_column]
                    if mask.any():
                        # Update existing row
                        for col in data_with_timestamp.columns:
                            updated_data.loc[mask, col] = new_row[col]
                    else:
                        # Append new row
                        updated_data = pd.concat([updated_data, new_row.to_frame().T], ignore_index=True)
                
                # Write back to sheet
                return self.write(updated_data.drop(columns=['last_updated'], errors='ignore'))
            else:
                # If ID column not found, just append
                return self.update(data)
            
        except Exception as e:
            self.logger.error(f"Failed to upsert to Google Sheets: {str(e)}")
            return False
    
    def _format_header_row(self, worksheet: gspread.Worksheet):
        """Format the header row with bold text and background color"""
        try:
            # Get the number of columns
            data = worksheet.get_all_values()
            if data:
                num_cols = len(data[0])
                
                # Format header row
                worksheet.format('1:1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
                
                # Auto-resize columns
                worksheet.columns_auto_resize(0, num_cols)
                
        except Exception as e:
            self.logger.warning(f"Failed to format header row: {str(e)}")
    
    def get_spreadsheet_url(self) -> Optional[str]:
        """Get the URL of the spreadsheet"""
        try:
            if not self._spreadsheet:
                self._spreadsheet = self._get_or_create_spreadsheet()
            return self._spreadsheet.url
        except Exception:
            return None
    
    def backup_to_csv(self, filename: Optional[str] = None) -> bool:
        """
        Create a CSV backup of the Google Sheets data
        
        Args:
            filename: Optional filename for the backup
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            worksheet = self._get_or_create_worksheet()
            data = pd.DataFrame(worksheet.get_all_records())
            
            if data.empty:
                self.logger.warning("No data to backup")
                return True
            
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"backup_yad2_properties_{timestamp}.csv"
            
            data.to_csv(filename, index=False)
            self.logger.info(f"Successfully created backup: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {str(e)}")
            return False