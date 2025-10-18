import os
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ScraperConfig:
    """Configuration for Yad2 scraper"""
    url: str = "https://www.yad2.co.il/realestate/rent"
    base_url: str = "https://www.yad2.co.il"
    base_item_url: str = "https://www.yad2.co.il/realestate/item/"
    headers: Dict[str, str] = None
    request_delay: float = 1.0  # seconds between requests
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


@dataclass
class GoogleSheetsConfig:
    """Configuration for Google Sheets integration"""
    credentials_file: str = "config/credentials.json"
    spreadsheet_name: str = "Yad2 Properties"
    worksheet_name: str = "Properties"


@dataclass
class DatabaseConfig:
    """Configuration for local data storage"""
    backup_csv_path: str = "data/properties_backup.csv"
    max_rows_per_sheet: int = 1000


class Settings:
    """Main settings class that aggregates all configurations"""
    
    def __init__(self):
        self.scraper = ScraperConfig()
        self.google_sheets = GoogleSheetsConfig()
        self.database = DatabaseConfig()
        
        # Load environment variables
        self._load_from_env()
    
    def _load_from_env(self):
        """Load settings from environment variables"""
        # Google Sheets settings
        if os.getenv('GOOGLE_CREDENTIALS_FILE'):
            self.google_sheets.credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
        if os.getenv('SPREADSHEET_NAME'):
            self.google_sheets.spreadsheet_name = os.getenv('SPREADSHEET_NAME')
        if os.getenv('WORKSHEET_NAME'):
            self.google_sheets.worksheet_name = os.getenv('WORKSHEET_NAME')
        if os.getenv('SPREADSHEET_ID'):
            self.google_sheets.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        
        # Scraper settings
        if os.getenv('REQUEST_DELAY'):
            self.scraper.request_delay = float(os.getenv('REQUEST_DELAY'))


# Global settings instance
settings = Settings()