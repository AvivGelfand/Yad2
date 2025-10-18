# Yad2 Real Estate Scraper with Google Sheets Integration

A comprehensive Python scraper for Yad2.co.il real estate listings with automated Google Sheets integration and CSV export capabilities.

## 🚀 Features

- **Multi-page scraping**: Automatically fetches listings across multiple pages
- **Google Sheets integration**: Direct upload and update of data to Google Sheets
- **CSV export**: Local backup and standalone CSV file generation
- **Duplicate handling**: Smart upsert functionality to avoid duplicate entries
- **Two scraping modes**: 
  - **Basic**: Fast extraction of essential listing information
  - **Detailed**: Comprehensive data including property features, coordinates, and descriptions
- **Configurable search parameters**: Customizable price range, location, property features
- **Robust error handling**: Automatic retry and fallback mechanisms
- **Logging**: Comprehensive logging for monitoring and debugging

## 📁 Project Structure

```
Yad2/
├── README.md
├── requirements.txt
├── .env.example                    # Environment variables template
├── .gitignore
├── config/
│   ├── settings.py                 # Centralized configuration
│   └── credentials.json.example    # Google API credentials template
├── src/
│   ├── scrapers/
│   │   ├── base_scraper.py         # Base scraper functionality
│   │   └── yad2_scraper.py         # Yad2-specific scraping logic
│   ├── writers/
│   │   ├── base_writer.py          # Base writer interface
│   │   ├── csv_writer.py           # CSV export functionality
│   │   └── google_sheets_writer.py # Google Sheets integration
│   └── models/
│       └── property.py             # Property data model
├── scripts/
│   ├── run_scraper.py              # Main execution script
│   └── setup_credentials.py       # Google API setup helper
└── tests/
    └── (test files)
```

## 🛠️ Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Google Sheets API Setup (Optional)

For Google Sheets integration, you need to set up Google API credentials:

```bash
python scripts/setup_credentials.py
```

Follow the detailed instructions provided by the setup script to:
1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a Service Account
4. Download credentials JSON file
5. Save as `config/credentials.json`

### 3. Environment Configuration

Copy the environment template and customize:

```bash
cp .env.example .env
```

Edit `.env` with your preferences:
```env
GOOGLE_CREDENTIALS_FILE=config/credentials.json
SPREADSHEET_NAME=Yad2 Properties
WORKSHEET_NAME=Properties
SHARE_WITH_EMAIL=your-email@example.com
REQUEST_DELAY=1.0
```

## 🎯 Usage

### Basic Usage

```bash
# Run with default settings (detailed mode, both outputs)
python scripts/run_scraper.py

# Fast scraping with CSV output only
python scripts/run_scraper.py --mode basic --output csv

# Google Sheets only with detailed data
python scripts/run_scraper.py --mode detailed --output sheets
```

### Advanced Options

```bash
python scripts/run_scraper.py \
    --mode detailed \
    --output both \
    --max-listings 50 \
    --backup \
    --log-level DEBUG
```

### Command Line Arguments

- `--mode`: Scraping mode (`basic` or `detailed`)
- `--output`: Output destination (`sheets`, `csv`, or `both`)
- `--max-listings`: Maximum number of listings to process
- `--backup`: Create CSV backup even when using Google Sheets
- `--log-level`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## 📊 Data Fields

### Basic Mode Fields
- `listing_id`: Unique listing identifier
- `price_ils`: Rental price in Israeli Shekels
- `city`: City name
- `neighborhood`: Neighborhood
- `street`: Street address
- `rooms`: Number of rooms
- `area_sqm`: Property area in square meters
- `property_type`: Type of property
- `created_at`: Listing creation date

### Detailed Mode Additional Fields
- `ad_number`: Yad2 ad number
- `floor`: Floor number
- `total_floors`: Total floors in building
- `entry_date`: Available entry date
- `description`: Property description
- `monthly_arnona_ils`: Monthly municipal tax
- `monthly_vaad_ils`: Monthly building committee fee
- `has_elevator`: Elevator availability
- `has_parking`: Parking availability
- `has_balcony`: Balcony availability
- `has_mamad`: Safe room (Mamad) availability
- `is_renovated`: Renovation status
- `latitude`: GPS latitude
- `longitude`: GPS longitude
- `image_count`: Number of property images
- `last_updated`: Data update timestamp

## ⚙️ Configuration

### Search Parameters

Modify search parameters in `config/settings.py` or environment variables:

```python
# Default search parameters
params = {
    "minPrice": "3000",
    "maxPrice": "10000", 
    "minRooms": "3",
    "maxRooms": "4.5",
    "city": "6400",  # Tel Aviv
    "elevator": "1",
    "balcony": "1",
    "renovated": "1"
}
```

### Google Sheets Configuration

```python
# Google Sheets settings
SPREADSHEET_NAME = "Yad2 Properties"
WORKSHEET_NAME = "Properties" 
SHARE_WITH_EMAIL = "your-email@example.com"
```

## 🔧 API Integration

### Using the Scraper Programmatically

```python
from src.scrapers.yad2_scraper import Yad2Scraper
from src.writers.google_sheets_writer import GoogleSheetsWriter

# Initialize scraper
scraper = Yad2Scraper()

# Fetch listings
listings = scraper.fetch_listings()

# Get detailed data
df = scraper.scrape_detailed_listings(listings)

# Upload to Google Sheets
writer = GoogleSheetsWriter()
writer.upsert_by_id(df, 'listing_id')
```

### Google Sheets Writer Methods

```python
writer = GoogleSheetsWriter()

# Write data (overwrites existing)
writer.write(dataframe)

# Update data (append new rows)
writer.update(dataframe)

# Upsert data (update existing, insert new)
writer.upsert_by_id(dataframe, 'listing_id')

# Clear all data
writer.clear()

# Create CSV backup
writer.backup_to_csv()

# Get spreadsheet URL
url = writer.get_spreadsheet_url()
```

## 🐛 Troubleshooting

### Common Issues

1. **Google Sheets Authentication Error**
   ```bash
   python scripts/setup_credentials.py validate
   ```

2. **Import Errors**
   ```bash
   pip install -r requirements.txt
   ```

3. **No Data Found**
   - Check internet connection
   - Verify search parameters aren't too restrictive
   - Check if Yad2 website structure has changed

4. **Rate Limiting**
   - Increase `REQUEST_DELAY` in settings
   - Use `--max-listings` for testing

### Debugging

Enable debug logging for detailed information:

```bash
python scripts/run_scraper.py --log-level DEBUG
```

Log files are automatically created as `scraper.log`.

## 📄 License

This project is for educational and personal use only. Please respect Yad2's terms of service and implement appropriate rate limiting.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## ⚠️ Disclaimer

This scraper is intended for personal use and educational purposes. Users are responsible for compliance with Yad2's terms of service and applicable laws. The authors are not responsible for any misuse of this software. Rental Apartments Scraper

This project scrapes rental apartment posts from [Yad2 Real Estate Rent](https://www.yad2.co.il/realestate/rent).

## Features
- Fetches and parses rental listings
- Outputs data in a structured format

## Setup
1. Create a virtual environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Usage
Run the scraper:
```sh
python src/scraper.py
```

## Testing
Run tests with:
```sh
python -m unittest discover tests
```

---
Replace or extend the scraper logic in `src/scraper.py` as needed.
