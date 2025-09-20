# Yad2 Rental Apartments Scraper

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
