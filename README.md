# Yad2 Real Estate Scraper with Google Sheets & Telegram Integration

A comprehensive Python scraper for Yad2.co.il real estate listings with automated Google Sheets integration, Telegram notifications, and multi-search configuration support.

> **Current Status**: Active development project with core scraping, Google Sheets integration, and Telegram notifications fully functional.

## 🚀 Features

- **Multi-search configuration**: Run multiple search queries with different parameters
- **Google Sheets integration**: Direct upload and update of data with smart upsert functionality
- **Telegram notifications**: Real-time notifications for new properties found
- **Property tracking**: Avoid duplicate notifications using local property database
- **Duplicate handling**: Smart deduplication across multiple searches
- **Comprehensive data extraction**: Detailed property information including images, coordinates, and amenities
- **Manual column preservation**: Maintains user-added columns (decisions, notes, contacted status)
- **Robust error handling**: Automatic retry mechanisms and error notifications
- **🤖 GitHub Actions automation**: Run automatically every 30 minutes on GitHub (see [GitHub Actions Setup Guide](GITHUB_ACTIONS_SETUP.md))

## 📁 Project Structure

```
Yad2/
├── README.md
├── requirements.txt
├── .gitignore
├── .github/
│   └── copilot-instructions.md    # GitHub Copilot instructions
├── config/
│   ├── __init__.py
│   ├── settings.py                # Centralized configuration with environment loading
│   └── search_configs.py          # Search parameter configurations
├── src/
│   ├── __init__.py
│   └── writers/
│       ├── __init__.py
│       └── google_sheets_reader_writer.py  # Google Sheets integration
├── scripts/
│   ├── main.py                    # Main execution script
│   └── scraper.py                 # Core scraping functionality
├── notifications/
│   └── telegram_notifier.py       # Telegram notification system
└── utils/
    └── property_tracker.py        # Property tracking and deduplication
```

**Note**: Create the following files manually:
- `.env` - Environment variables (see configuration section below)
- `config/credentials.json` - Google API credentials
- `data/` directory and `seen_properties.json` - Created automatically when first run

## 🛠️ Setup

### Prerequisites
- Python 3.7 or higher
- Virtual environment (recommended)

### 1. Install Dependencies

```bash
# Create virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note**: The scraper will automatically create the `data/` directory and `seen_properties.json` file on first run.

### 2. Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Sheets API
4. Create a Service Account
5. Download the credentials JSON file
6. Save as `config/credentials.json`
7. Share your Google Sheet with the service account email

### 3. Telegram Bot Setup (Optional)

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Save the bot token
4. Get your chat ID by messaging your bot and visiting: `https://api.telegram.org/bot<TOKEN>/getUpdates`

**Note**: If you don't set up Telegram, notifications will be disabled automatically.

### 4. Environment Configuration

Create a `.env` file in the project root with your credentials:

```env
# Google Sheets Configuration
GOOGLE_CREDENTIALS_FILE=config/credentials.json
SPREADSHEET_NAME=Yad2 Properties
WORKSHEET_NAME=Properties
SPREADSHEET_ID=your_spreadsheet_id_here

# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Notification Settings
ENABLE_NOTIFICATIONS=true
NOTIFY_ON_NEW_PROPERTIES=true
NOTIFY_ON_ERROR=true

# Database (optional - will be created automatically)
DATABASE_PATH=data/seen_properties.json

# Request delay (optional)
REQUEST_DELAY=1.0
```

## 🤖 GitHub Actions Automation

Want the scraper to run automatically every 30 minutes? Set it up on GitHub Actions!

**📖 See the complete guide**: [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md)

**Quick Overview**:
1. Push your code to GitHub
2. Set up GitHub Secrets (credentials, API keys)
3. Enable GitHub Actions
4. The scraper runs automatically every 30 minutes!

**Benefits**:
- ✅ Fully automated - no manual intervention needed
- ✅ Runs 24/7 on GitHub's servers
- ✅ Free for public repositories (unlimited runs)
- ✅ Local execution still works the same way
- ✅ State persists between runs

## 🎯 Usage

### Basic Usage

```bash
# Run the scraper with all configured searches
python scripts/main.py
```

The script will:
1. Run all search configurations defined in `config/search_configs.py`
2. Combine results and remove duplicates
3. Update Google Sheets with new/updated properties
4. Send Telegram notifications for new properties (if configured)
5. Display summary statistics

### Search Configuration

Edit `config/search_configs.py` to customize your searches:

```python
SEARCH_CONFIGURATIONS = [
    {
        "name": "Elevator Properties",
        "params": {
            "city": "6400",        # Tel Aviv
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "8500",
            "elevator": "1",
            "balcony": "1",
            "renovated": "1"
        }
    },
    # Add more search configurations...
]
```

## 📊 Data Fields

The scraper extracts comprehensive property information:

### Core Fields
- `listing_id`: Unique listing identifier
- `ad_number`: Yad2 ad number
- `rent`: Monthly rent price
- `city`, `neighborhood`, `street`: Location details
- `rooms`: Number of rooms
- `sqm`: Property area in square meters
- `floor`, `total_floors`: Floor information

### Property Features
- `elevator`: Elevator availability (boolean)
- `parking`: Parking availability (boolean)
- `balcony`: Balcony availability (boolean)
- `mamad`: Safe room availability (boolean)
- `AC`: Air conditioning (boolean)
- `renovated`: Renovation status (boolean)
- `furniture`: Furniture information
- `pets`: Pet policy

### Financial Details
- `arnona_month`: Monthly municipal tax
- `vaad`: Monthly building committee fee
- `entry_date`: Available entry date

### Media & Location
- `latitude`, `longitude`: GPS coordinates
- `images`: Property image URLs
- `image_count`: Number of images
- `video_count`: Number of videos
- `description`: Property description

### Tracking Fields
- `created_at`, `updated_at`: Yad2 timestamps
- `search_timestamp`: When scraped
- `found_in_searches`: Which searches found this property
- `last_scraped_at`: Last update timestamp

### Lifecycle Tracking Fields
These fields track the complete lifecycle of each listing:

- `first_seen_date`: Datetime when the listing first appeared in any scrape
- `last_seen_date`: Datetime of the last scrape where the listing was found
- `change_dates`: List of datetimes when changes were detected (separated by '; ')
- `change_history`: Detailed log of what changed with timestamps (format: `[timestamp] field: old→new`)
- `removed_date`: Datetime when the listing was no longer found (empty if still active)

**Note**: These columns replace the old `status` column with much more detailed tracking:
- **New listings**: `first_seen_date` = `last_seen_date` and no changes
- **Updated listings**: `change_dates` and `change_history` show what changed
- **Removed listings**: `removed_date` is set with timestamp

### Manual Columns (Preserved)
- `decision`: Your decision on the property
- `notes`: Personal notes
- `contacted`: Contact status

## 🔧 Configuration

### Settings Management

The project uses a centralized configuration system in `config/settings.py` that:
- Loads environment variables from `.env` file automatically
- Provides default values for all settings
- Supports both environment variables and direct configuration

### Search Parameters

Common search parameters you can use in `search_configs.py`:

```python
params = {
    "city": "6400",           # City ID (6400 = Tel Aviv)
    "minPrice": "3000",       # Minimum rent
    "maxPrice": "10000",      # Maximum rent
    "minRooms": "3",          # Minimum rooms
    "maxRooms": "4.5",        # Maximum rooms
    "minFloor": "0",          # Minimum floor
    "maxFloor": "10",         # Maximum floor
    "elevator": "1",          # Has elevator
    "balcony": "1",           # Has balcony
    "parking": "1",           # Has parking
    "renovated": "1",         # Is renovated
    "imageOnly": "1",         # Only listings with images
    "priceOnly": "1",         # Only listings with price
}
```

### Notification Settings

Control notifications in your `.env` file:

```env
ENABLE_NOTIFICATIONS=true
NOTIFY_ON_NEW_PROPERTIES=true    # Notify for new properties
NOTIFY_ON_ERROR=true            # Notify on scraping errors
```

## 🔔 Telegram Notifications

The scraper sends formatted notifications for new properties:

```
🏠 New Property Found!

💰 Rent: ₪7,500
📍 Location: Rothschild Blvd, Center
🏠 Rooms: 4
📐 Area: 85 sqm
🏢 Floor: 3
🛗 Elevator: ✅ Yes

[View Property](https://yad2.co.il/...)

⏰ Found: 2025-10-19 14:30
```

## 🗃️ Google Sheets Integration

### Features
- **Smart upsert**: Updates existing listings, adds new ones
- **Manual column preservation**: Your notes and decisions are never overwritten
- **Backup functionality**: Optional backup creation (currently commented out in main.py)
- **Status tracking**: Tracks which properties are new, updated, or missing

### Manual Columns

Add these columns to your sheet for manual tracking:
- `decision`: Your decision (interested/not interested/maybe)
- `notes`: Personal notes about the property
- `contacted`: Whether you've contacted the owner

These columns will never be overwritten by the scraper.

## 🧪 Testing

The project includes comprehensive test coverage for the lifecycle tracking functionality.

### Running Tests

```bash
# Run all tests
python3 -m unittest discover tests -v

# Run unit tests only
python3 -m unittest tests.test_lifecycle_tracking -v

# Run integration tests only
python3 -m unittest tests.test_integration -v
```

### Test Coverage

- **23 total tests** covering all lifecycle tracking functionality
- **18 unit tests** for change detection and lifecycle logic
- **5 integration tests** for end-to-end workflows

See `tests/TEST_SUMMARY.md` for detailed test documentation.

## 🐛 Troubleshooting

### Common Issues

1. **Google Sheets Authentication Error**
   - Verify `config/credentials.json` exists and is valid
   - Check that the sheet is shared with your service account email
   - Verify `SPREADSHEET_ID` in `.env` is correct (if using specific spreadsheet ID)
   - Ensure `SPREADSHEET_NAME` matches your Google Sheet name exactly

2. **No New Properties Found**
   - Check if your search parameters are too restrictive
   - Verify internet connection
   - Check if Yad2's website structure has changed

3. **Telegram Notifications Not Working**
   - Verify bot token and chat ID in `.env`
   - Test bot connection manually
   - Check if bot is blocked or chat is deleted

4. **Import Errors**
   ```bash
   pip install -r requirements.txt
   ```

### Debugging

The scraper provides detailed console output. Check for:
- ✅ Successful operations
- ⚠️ Warnings
- ❌ Errors
- 📱 Notification status

## 📄 License

This project is for educational and personal use only. Please respect Yad2's terms of service and implement appropriate rate limiting.

## 📋 Setup Checklist

Before running the scraper, ensure you have:

- [ ] Created `.env` file with your configuration
- [ ] Set up Google Sheets API and downloaded `config/credentials.json`
- [ ] Configured at least one search in `config/search_configs.py`
- [ ] (Optional) Set up Telegram bot for notifications
- [ ] Installed all dependencies from `requirements.txt`

## ⚠️ Disclaimer

This scraper is intended for personal use and educational purposes. Users are responsible for compliance with Yad2's terms of service and applicable laws. The authors are not responsible for any misuse of this software.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

**Note**: Make sure to keep your credentials and API keys secure. Never commit them to version control.
