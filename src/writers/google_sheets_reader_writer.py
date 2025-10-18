import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd  
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config.settings import settings


class GoogleSheetsReaderWriter:
    """A class to handle reading and writing to a Google Sheet with incremental updates."""
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, credentials_file: Optional[str] = None, 
                 spreadsheet_name: Optional[str] = None,
                 worksheet_name: Optional[str] = None):
        """Initializes the Sheets service and stores the spreadsheet ID."""
        self.credentials_file = credentials_file or settings.google_sheets.credentials_file
        self.spreadsheet_name = spreadsheet_name or settings.google_sheets.spreadsheet_name
        self.worksheet_name = worksheet_name or settings.google_sheets.worksheet_name
        self.spreadsheet_id = settings.google_sheets.spreadsheet_id
        
        self.service = self._authenticate()
        if not self.service:
            raise ConnectionError("Failed to authenticate Google Sheets service.")

        self.last_update_column = 'last_scraped_at'
        # Fixed: Match the columns used in scraper
        self.manual_columns = {'decision', 'notes', 'contacted'}

    def _authenticate(self):
        """Authenticates with Google Sheets API using a Service Account."""
        try:
            # Load credentials from the JSON file
            creds = Credentials.from_service_account_file(
                self.credentials_file, scopes=self.SCOPES
            )
            
            # Build the Sheets API service object
            service = build('sheets', 'v4', credentials=creds)
            print("Successfully authenticated with Google Sheets API.")
            return service
        except Exception as e:
            print(f"Authentication Error: {e}")
            return None

    def read_sheet(self):
        """Reads data from a specified range (e.g., 'Sheet1!A1:B5')."""
        try:
            sheet = self.service.spreadsheets()
            # sheet._validate_credentials()
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id, 
                range=self.worksheet_name
            ).execute()
            
            values = result.get('values', [])
            if not values:
                print('No data found.')
                return []
            
            print(f"Read {len(values)} rows from {self.worksheet_name}.")
            return values
        except HttpError as err:
            print(f"An API error occurred: {err}")
            return []

    def write_sheet(self, values):
        """Writes data (a list of lists) to a specified range (e.g., 'Sheet1!A1')."""
        try:
            body = {'values': values}
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=self.worksheet_name,
                valueInputOption='USER_ENTERED', # Interprets input as if typed in a cell
                body=body
            ).execute()
            
            print(f"Cells updated: {result.get('updatedCells')} at range {result.get('updatedRange')}")
            return result
        except HttpError as err:
            print(f"An API error occurred: {err}")
            return None

    def read_sheet_as_dataframe(self) -> pd.DataFrame:
        """Reads the entire sheet and returns as a pandas DataFrame."""
        try:
            values = self.read_sheet()
            if not values:
                return pd.DataFrame()
            
            # First row contains headers
            headers = values[0]
            data = values[1:] if len(values) > 1 else []
            
            # Pad rows to match header length
            padded_data = []
            for row in data:
                padded_row = row + [''] * (len(headers) - len(row))
                padded_data.append(padded_row)
            
            df = pd.DataFrame(padded_data, columns=headers)
            return df
        except Exception as e:
            print(f"Error reading sheet as DataFrame: {e}")
            return pd.DataFrame()

    def get_existing_listing_ids(self) -> set:
        """Returns a set of existing listing IDs from the sheet."""
        df = self.read_sheet_as_dataframe()
        if df.empty or 'listing_id' not in df.columns:
            return set()
        return set(df['listing_id'].astype(str).tolist())

    def upsert_listings(self, new_df: pd.DataFrame, id_column: str = 'listing_id') -> Dict[str, int]:
        """
        Updates existing listings and inserts new ones.
        Returns a summary of operations performed.
        """
        existing_df = self.read_sheet_as_dataframe()
        current_time = datetime.now().isoformat()
        
        # Sanitize new data BEFORE merging to prevent broadcast errors
        new_df = new_df.copy()
        new_df = self._sanitize_dataframe(new_df)
        new_df[self.last_update_column] = current_time
        
        stats = {'new': 0, 'updated': 0, 'unchanged': 0}
        
        if existing_df.empty:
            # First time - write all data
            self._write_dataframe_to_sheet(new_df, skip_sanitization=True)
            stats['new'] = len(new_df)
        else:
            # Merge new data with existing
            merged_df = self._merge_dataframes(existing_df, new_df, id_column, current_time)
            
            # Calculate stats
            if id_column in existing_df.columns:
                existing_ids = set(existing_df[id_column].astype(str))
                new_ids = set(new_df[id_column].astype(str))
                stats['new'] = len(new_ids - existing_ids)
                stats['updated'] = len(new_ids & existing_ids)
            
            self._write_dataframe_to_sheet(merged_df, skip_sanitization=True)
        
        return stats
    def _merge_dataframes(self, existing_df: pd.DataFrame, new_df: pd.DataFrame, 
                        id_column: str, current_time: str) -> pd.DataFrame:
        """Merges new data with existing, preserving manual columns."""
        # Preserve original DataFrame column order plus manual columns
        # Start with new DataFrame columns (scraped data order)
        ordered_columns = list(new_df.columns)
        
        # Add existing columns that aren't in new_df (manual columns, etc.)
        for col in existing_df.columns:
            if col not in ordered_columns:
                ordered_columns.append(col)
        
        # Add missing columns with empty values
        for col in ordered_columns:
            if col not in existing_df.columns:
                existing_df[col] = ''
            if col not in new_df.columns:
                new_df[col] = ''
        
        # Reorder columns to match our desired order
        existing_df = existing_df[ordered_columns]
        new_df = new_df[ordered_columns]
        
        # Mark existing records that weren't found in new scrape
        new_ids = set(new_df[id_column].astype(str))
        existing_df.loc[~existing_df[id_column].astype(str).isin(new_ids), 'status'] = 'not_found_in_latest_scrape'
        
        # Update existing records with new data, preserving manual columns
        updated_df = existing_df.copy()
        for _, new_row in new_df.iterrows():
            listing_id = str(new_row[id_column])
            existing_mask = existing_df[id_column].astype(str) == listing_id
            
            if existing_mask.any():
                # Update existing record, but preserve manual columns
                for col in ordered_columns:
                    if col not in self.manual_columns and col != self.last_update_column:
                        # Get the index for direct assignment to avoid broadcast issues
                        idx = existing_df.index[existing_mask].tolist()[0]
                        updated_df.at[idx, col] = new_row[col]
                
                # Always update timestamp and status for existing records
                idx = existing_df.index[existing_mask].tolist()[0]
                updated_df.at[idx, self.last_update_column] = current_time
                updated_df.at[idx, 'status'] = 'updated'
            else:
                # Add new record with empty manual columns
                new_row_dict = new_row.to_dict()
                for manual_col in self.manual_columns:
                    new_row_dict[manual_col] = ''
                
                new_row_dict['status'] = 'new'
                updated_df = pd.concat([updated_df, pd.DataFrame([new_row_dict])], ignore_index=True)

        # Ensure final DataFrame maintains the column order
        return updated_df[ordered_columns]

    def _write_dataframe_to_sheet(self, df: pd.DataFrame, skip_sanitization: bool = False):
        """Writes a DataFrame to the sheet, replacing all content."""
        if df.empty:
            return
        
        # Sanitize complex data types before writing (unless already done)
        if not skip_sanitization:
            df_clean = self._sanitize_dataframe(df)
        else:
            df_clean = df
        
        # Convert DataFrame to list of lists for the API
        values = [df_clean.columns.tolist()] + df_clean.fillna('').values.tolist()
        
        # Clear the sheet first
        self.clear_sheet()
        
        # Write new data
        self.write_sheet(values)

    def _sanitize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sanitizes DataFrame to ensure all values are compatible with Google Sheets."""
        df_clean = df.copy()
        
        # Handle special columns first
        df_clean = self._handle_special_columns(df_clean)
        
        # Then sanitize remaining values
        for column in df_clean.columns:
            df_clean[column] = df_clean[column].apply(self._sanitize_value)
        
        return df_clean

    def _handle_special_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handles special column formatting before writing to sheets."""
        df_clean = df.copy()
        
        # Handle tags column specifically
        if 'tags' in df_clean.columns:
            df_clean['tags'] = df_clean['tags'].apply(
                lambda x: ', '.join([tag.get('name', str(tag)) for tag in x]) 
                if isinstance(x, list) and x else ''
            )
        
        # Handle images column
        if 'images' in df_clean.columns:
            df_clean['images'] = df_clean['images'].apply(
                lambda x: f"{len(x)} images" if isinstance(x, list) else str(x) if x else ''
            )
        
        return df_clean

    def _sanitize_value(self, value):
        """Converts complex data types to string representations."""
        if value is None:
            return ''
        elif isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                return str(value)
        elif isinstance(value, (int, float, bool)):
            return value
        elif isinstance(value, str):
            # Ensure string is not too long for Google Sheets (50,000 char limit)
            return value[:49999] if len(value) > 49999 else value
        else:
            return str(value)

    def clear_sheet(self):
        """Clears all content from the worksheet."""
        try:
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=self.worksheet_name
            ).execute()
            print(f"Cleared worksheet: {self.worksheet_name}")
        except HttpError as err:
            print(f"Error clearing sheet: {err}")

    def archive_old_listings(self, days_threshold: int = 30) -> int:
        """
        Moves listings not seen in recent scrapes to an archive sheet.
        Returns number of archived listings.
        """
        df = self.read_sheet_as_dataframe()
        if df.empty or self.last_update_column not in df.columns:
            return 0
        
        # Convert timestamps and find old listings
        df[self.last_update_column] = pd.to_datetime(df[self.last_update_column], errors='coerce')
        cutoff_date = datetime.now() - pd.Timedelta(days=days_threshold)
        
        old_mask = df[self.last_update_column] < cutoff_date
        old_listings = df[old_mask]
        current_listings = df[~old_mask]
        
        if not old_listings.empty:
            # Write old listings to archive sheet
            archive_sheet_name = f"{self.worksheet_name}_Archive"
            self._ensure_archive_sheet_exists(archive_sheet_name)
            
            # Append to archive (you might want to implement append_to_sheet method)
            # For now, we'll just remove them from main sheet
            self._write_dataframe_to_sheet(current_listings)
            
        return len(old_listings)

    def _ensure_archive_sheet_exists(self, archive_sheet_name: str):
        """Creates archive sheet if it doesn't exist."""
        try:
            # Try to get the sheet metadata to see if archive sheet exists
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_names = [sheet['properties']['title'] for sheet in sheet_metadata['sheets']]
            
            if archive_sheet_name not in sheet_names:
                # Create the archive sheet
                request_body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {
                                'title': archive_sheet_name
                            }
                        }
                    }]
                }
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=request_body
                ).execute()
                
                print(f"Created archive sheet: {archive_sheet_name}")
                
        except HttpError as err:
            print(f"Error managing archive sheet: {err}")

    def get_update_summary(self) -> Dict[str, Any]:
        """Returns summary statistics about the current sheet state."""
        df = self.read_sheet_as_dataframe()
        if df.empty:
            return {'total_listings': 0}
        
        summary = {
            'total_listings': len(df),
            'last_update': datetime.now().isoformat()
        }
        
        if 'status' in df.columns:
            status_counts = df['status'].value_counts().to_dict()
            summary.update(status_counts)
        
        if self.last_update_column in df.columns:
            df[self.last_update_column] = pd.to_datetime(df[self.last_update_column], errors='coerce')
            latest_scrape = df[self.last_update_column].max()
            if pd.notna(latest_scrape):
                summary['latest_scrape_time'] = latest_scrape.isoformat()
        
        return summary

    def backup_sheet(self, backup_suffix: str = None) -> str:
        """
        Creates a backup copy of the current sheet.
        Returns the name of the backup sheet.
        """
        if not backup_suffix:
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_sheet_name = f"{self.worksheet_name}_backup_{backup_suffix}"
        
        try:
            # Read current data
            df = self.read_sheet_as_dataframe()
            
            # Create backup sheet and write data
            self._ensure_archive_sheet_exists(backup_sheet_name)
            
            # Switch to backup sheet temporarily
            original_worksheet = self.worksheet_name
            self.worksheet_name = backup_sheet_name
            self._write_dataframe_to_sheet(df)
            self.worksheet_name = original_worksheet
            
            print(f"Created backup: {backup_sheet_name}")
            return backup_sheet_name
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None

    def get_manual_columns_summary(self) -> Dict[str, Any]:
        """Returns summary of manual column usage."""
        df = self.read_sheet_as_dataframe()
        if df.empty:
            return {}
        
        summary = {}
        for col in self.manual_columns:
            if col in df.columns:
                filled_count = df[col].notna().sum() - (df[col] == '').sum()
                summary[f'{col}_filled'] = int(filled_count)
                summary[f'{col}_total'] = len(df)
        
        return summary

    def add_manual_column(self, column_name: str, default_value: str = ''):
        """Adds a new manual column to the sheet."""
        # Add to manual columns set
        self.manual_columns.add(column_name)
        
        df = self.read_sheet_as_dataframe()
        if not df.empty and column_name not in df.columns:
            df[column_name] = default_value
            self._write_dataframe_to_sheet(df)
            print(f"Added manual column: {column_name}")
        elif df.empty:
            print(f"Sheet is empty, manual column '{column_name}' will be added on first data write")
        else:
            print(f"Manual column '{column_name}' already exists")

    def update_manual_data(self, listing_id: str, column_name: str, value: str) -> bool:
        """Updates a manual column for a specific listing."""
        if column_name not in self.manual_columns:
            print(f"Warning: {column_name} is not configured as a manual column")
        
        df = self.read_sheet_as_dataframe()
        if df.empty or 'listing_id' not in df.columns:
            return False
        
        mask = df['listing_id'].astype(str) == str(listing_id)
        if mask.any():
            df.loc[mask, column_name] = value
            self._write_dataframe_to_sheet(df)
            print(f"Updated {column_name} for listing {listing_id}")
            return True
        
        print(f"Listing {listing_id} not found")
        return False
