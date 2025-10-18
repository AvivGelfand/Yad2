#!/usr/bin/env python3
"""
Helper script to set up Google Sheets API credentials
"""

import os
import json
import sys
from pathlib import Path


def create_credentials_setup():
    """Guide user through setting up Google Sheets API credentials"""
    
    print("🔧 Google Sheets API Setup Guide")
    print("=" * 40)
    print()
    print("To use Google Sheets integration, you need to:")
    print("1. Create a Google Cloud Project")
    print("2. Enable the Google Sheets API")
    print("3. Create a Service Account")
    print("4. Download the credentials JSON file")
    print()
    
    print("📋 Step-by-step instructions:")
    print()
    print("1. Go to: https://console.cloud.google.com/")
    print("2. Create a new project or select existing one")
    print("3. Enable Google Sheets API:")
    print("   - Go to 'APIs & Services' > 'Library'")
    print("   - Search for 'Google Sheets API'")
    print("   - Click 'Enable'")
    print()
    print("4. Create Service Account:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click 'Create Credentials' > 'Service Account'")
    print("   - Fill in the details and create")
    print()
    print("5. Download JSON key:")
    print("   - Click on the created service account")
    print("   - Go to 'Keys' tab")
    print("   - Click 'Add Key' > 'Create new key' > 'JSON'")
    print("   - Download the file")
    print()
    
    # Check if config directory exists
    config_dir = Path("config")
    if not config_dir.exists():
        print("❌ Config directory not found. Are you running this from the project root?")
        sys.exit(1)
    
    credentials_path = config_dir / "credentials.json"
    
    print(f"6. Save the downloaded file as: {credentials_path}")
    print()
    
    # Check if credentials already exist
    if credentials_path.exists():
        print("✅ Credentials file already exists!")
        
        # Validate the credentials file
        try:
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
            
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in creds]
            
            if missing_fields:
                print(f"⚠️  Credentials file is missing required fields: {missing_fields}")
            else:
                print("✅ Credentials file appears to be valid!")
                print(f"   Service Account Email: {creds.get('client_email')}")
                print(f"   Project ID: {creds.get('project_id')}")
                
        except json.JSONDecodeError:
            print("❌ Credentials file exists but contains invalid JSON")
        except Exception as e:
            print(f"❌ Error reading credentials file: {str(e)}")
    else:
        print("❌ Credentials file not found.")
        print(f"   Please save your downloaded JSON file as: {credentials_path}")
    
    print()
    print("🔒 Security Notes:")
    print("- Never commit credentials.json to version control")
    print("- The credentials.json file is already in .gitignore")
    print("- Keep your service account key secure")
    print()
    
    # Check environment file
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📝 Environment Configuration:")
        print(f"   Copy {env_example} to {env_file} and update the values")
        
        response = input("Would you like me to copy .env.example to .env? (y/N): ")
        if response.lower() == 'y':
            try:
                with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                    dst.write(src.read())
                print("✅ Created .env file from template")
                print("   Please edit .env file with your specific settings")
            except Exception as e:
                print(f"❌ Failed to copy .env file: {str(e)}")
    
    print()
    print("🚀 Next Steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Configure .env file with your settings")
    print("3. Run the scraper: python scripts/run_scraper.py")
    print()


def validate_installation():
    """Validate that all required packages are installed"""
    print("🔍 Checking required packages...")
    
    required_packages = [
        'gspread',
        'google-auth',
        'pandas',
        'requests',
        'beautifulsoup4'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print()
        print("📦 Missing packages found. Install them with:")
        print(f"pip install {' '.join(missing_packages)}")
        print()
        print("Or install all requirements:")
        print("pip install -r requirements.txt")
    else:
        print()
        print("✅ All required packages are installed!")
    
    return len(missing_packages) == 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'validate':
        validate_installation()
    else:
        create_credentials_setup()


if __name__ == "__main__":
    main()