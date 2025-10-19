# Yad2 Real Estate Scraper with Google Sheets & Telegram Integration

A comprehensive Python scraper for Yad2.co.il real estate listings with automated Google Sheets integration, Telegram notifications, and multi-search configuration support.

## 🚀 Features

- **Multi-search configuration**: Run multiple search queries with different parameters
- **Google Sheets integration**: Direct upload and update of data with smart upsert functionality
- **Telegram notifications**: Real-time notifications for new properties found
- **Property tracking**: Avoid duplicate notifications using local property database
- **Duplicate handling**: Smart deduplication across multiple searches
- **Comprehensive data extraction**: Detailed property information including images, coordinates, and amenities
- **Manual column preservation**: Maintains user-added columns (decisions, notes, contacted status)
- **Robust error handling**: Automatic retry mechanisms and error notifications

## 📁 Project Structure

```
Yad2/
├── README.md
├── requirements.txt
├── .env                           # Environment variables (copy from .env.example)
├── .gitignore
├── config/
│   ├── settings.py                # Centralized configuration
│   ├── search_configs.py          # Search parameter configurations
│   └── credentials.json           # Google API credentials (create manually)
├── src/
│   └── writers/
│       └── google_sheets_reader_writer.py  # Google Sheets integration
├── scripts/
│   ├── main.py                    # Main execution script
│   └── scraper.py                 # Core scraping functionality
├── notifications/
│   └── telegram_notifier.py       # Telegram notification system
├── utils/
│   └── property_tracker.py        # Property tracking and deduplication
└── data/
    └── seen_properties.json       # Local database of seen properties
```

## 🛠️ Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

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

### 4. Environment Configuration

Copy and customize the environment file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

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

# Database
DATABASE_PATH=data/seen_properties.json
```

## 🎯 Usage

### Basic Usage

```bash
# Run the scraper with all configured searches
python scripts/main.py
```

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
- `status`: Property status (new, updated, etc.)
- `last_scraped_at`: Last update timestamp

### Manual Columns (Preserved)
- `decision`: Your decision on the property
- `notes`: Personal notes
- `contacted`: Contact status

## 🔧 Configuration

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
- **Backup functionality**: Creates backups before major updates
- **Status tracking**: Tracks which properties are new, updated, or missing

### Manual Columns

Add these columns to your sheet for manual tracking:
- `decision`: Your decision (interested/not interested/maybe)
- `notes`: Personal notes about the property
- `contacted`: Whether you've contacted the owner

These columns will never be overwritten by the scraper.

## 🐛 Troubleshooting

### Common Issues

1. **Google Sheets Authentication Error**
   - Verify `config/credentials.json` exists and is valid
   - Check that the sheet is shared with your service account email
   - Verify `SPREADSHEET_ID` in `.env` is correct

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
