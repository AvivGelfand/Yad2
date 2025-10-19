import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import sys
import os
# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.search_configs import SEARCH_CONFIGURATIONS, SCRAPER_CONFIG
from config.settings import settings
from notifications.telegram_notifier import TelegramNotifier
from utils.property_tracker import PropertyTracker



class Yad2Scraper:
    def __init__(self, url=None, headers=None, params=None):
        self.url = url or SCRAPER_CONFIG["url"]
        self.headers = headers if headers is not None else SCRAPER_CONFIG["headers"]

    def fetch_listings(self, params=None):
        all_listings = []
        current_page = 1
        
        print(f"Fetching listings with params: {params}")
        
        while current_page <= 5:  # Limit to 5 pages per search to avoid too many requests
            print(f"Fetching page {current_page}...")
            current_params = {**params, 'page': current_page}
            
            try:
                # Make the web request for the current page
                response = requests.get(self.url, params=current_params, headers=self.headers)
                response.raise_for_status()
                
                # Parse the response
                soup = BeautifulSoup(response.text, 'html.parser')
                script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
                
                if not script_tag:
                    print(f"Could not find data on page {current_page}. Stopping.")
                    break

                data = json.loads(script_tag.string)
                feed = data.get('props', {}).get('pageProps', {}).get('feed', {})
                
                # Get listings from this page
                page_listings = []
                page_listings.extend(feed.get('private', [])) 
                page_listings.extend(feed.get('platinum', []))  
                page_listings.extend(feed.get('agency', []))
                
                if not page_listings:
                    print(f"No listings found on page {current_page}. Stopping.")
                    break
                    
                all_listings.extend(page_listings)
                print(f"Found {len(page_listings)} listings on page {current_page}")
                
                current_page += 1
                time.sleep(1)  # Be respectful to the server

            except requests.exceptions.RequestException as e:
                print(f"An error occurred during the request: {e}")
                break
            except json.JSONDecodeError:
                print(f"Failed to parse JSON on page {current_page}. Content might be invalid.")
                break
        
        print(f"Total listings found: {len(all_listings)}")
        return all_listings
    
    def scrape_listings_pages(self, listings):
        all_properties = []
        for listing in listings:
            full_url = SCRAPER_CONFIG["base_item_url"] + listing['token']
            property_details = self.scrape_listing_page(full_url)
            if property_details:
                all_properties.append(property_details)
        if all_properties: 
            df = pd.DataFrame(all_properties)
            # print(df.head())
            
        return df

    def scrape_listing_page(self, listing_url):
        print(f"Scraping individual listing page: {listing_url}")
        response = requests.get(listing_url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # print(soup.prettify()[:1000])  # Print the first 1000 characters of the page for inspection
        # ---
        # 2. Find all the <li> elements that are individual listings
        # We use the 'data-nagish' attribute as it's a consistent identifier.
        # listings = soup.find_all('li', attrs={'data-nagish': 'feed-item-list-box'})
        try:
            # Find the specific script tag by its ID
            script_tag = soup.find('script', {'id': '__NEXT_DATA__'})

            # Extract the JSON string and parse it into a Python dictionary
            data = json.loads(script_tag.string)

            # The actual listing data is nested; this path navigates to it
            # Try index 1 first, then fallback to index 0 if it fails
            try:
                listing_data = data['props']['pageProps']['dehydratedState']['queries'][1]['state']['data']
            except (KeyError, IndexError) as e:
                print(f"Failed to access index 1: {e}")
                try:
                    listing_data = data['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']
                except (KeyError, IndexError) as e:
                    print(f"Failed to access index 0: {e}")
                    listing_data = None

        except (AttributeError, KeyError, IndexError, TypeError) as e:
            print(f"Error finding or parsing data: {e}")
            listing_data = None # Set to None if data can't be found

        if listing_data:
            # Extract images more robustly
            images_data = listing_data.get('metaData', {}).get('images', [])
            
            # Handle different possible image data structures
            image_urls = []
            if isinstance(images_data, list):
                for img in images_data:
                    if isinstance(img, str):
                        # If the image is already a URL string
                        image_urls.append(img)
                    elif isinstance(img, dict):
                        # If the image is an object, try to get the URL from common fields
                        url = img.get('url') or img.get('src') or img.get('href') or img.get('link')
                        if url:
                            image_urls.append(url)
                        # Sometimes images are nested deeper
                        elif 'original' in img:
                            image_urls.append(img['original'])
                        elif 'large' in img:
                            image_urls.append(img['large'])
            # Create a dictionary to hold the extracted info for one listing
            property_details = {
                'listing_id': listing_data.get('token'),
                'ad_number': listing_data.get('adNumber'),
                'city': listing_data.get('address', {}).get('city', {}).get('text'),
                'created_at': listing_data.get('dates', {}).get('createdAt'),
                'updated_at': listing_data.get('dates', {}).get('updatedAt'),
                'neighborhood': listing_data.get('address', {}).get('neighborhood', {}).get('text'),
                'street': listing_data.get('address', {}).get('street', {}).get('text'),
                'rent': listing_data.get('price'),
                # Calculate monthly arnona (it's given for two months)
                'arnona_month': listing_data.get('propertyTax', 0) / 2 if listing_data.get('propertyTax') and listing_data.get('propertyTax') > 0 else None,
                'vaad': listing_data.get('houseCommittee'),
                'rooms': listing_data.get('additionalDetails', {}).get('roomsCount'),
                'sqm': listing_data.get('additionalDetails', {}).get('squareMeter'),
                'floor': listing_data.get('address', {}).get('house', {}).get('floor'),
                'elevator': listing_data.get('inProperty', {}).get('includeElevator'),
                'total_floors': listing_data.get('additionalDetails', {}).get('buildingTopFloor'),
                'condition': listing_data.get('additionalDetails', {}).get('propertyCondition', {}).get('text'),
                'entry_date': listing_data.get('additionalDetails', {}).get('entranceDate', '').split('T')[0],
                'description': listing_data.get('metaData', {}).get('description'),
                'search_text': listing_data.get('metaData', {}).get('searchText'),
                'isLongTermContract': listing_data.get('additionalDetails', {}).get('isLongTermContract'),
                'parking': listing_data.get('inProperty', {}).get('includeParking'),
                'balcony': listing_data.get('inProperty', {}).get('includeBalcony'),
                'mamad': listing_data.get('inProperty', {}).get('includeSecurityRoom'),
                'AC': listing_data.get('inProperty', {}).get('includeAirconditioner'),
                'Boiler': listing_data.get('inProperty', {}).get('includeBoiler'),
                'renovated': listing_data.get('inProperty', {}).get('isRenovated'),
                'furniture': listing_data.get('furnitureInfo', ''),
                'pets': listing_data.get('inProperty', {}).get('isPetsAllowed'),
                'latitude': listing_data.get('address', {}).get('coords', {}).get('lat'),
                'longitude': listing_data.get('address', {}).get('coords', {}).get('lon'),
                'tags': listing_data.get('tags', []),
                'property_type': listing_data.get('additionalDetails', {}).get('property', {}).get('text'),
                'link': listing_url,
                'image_count': len(listing_data.get('metaData', {}).get('images', [])),
                'images': image_urls,  # Now a clean list of URL strings
                'video_count': len(listing_data.get('metaData', {}).get('videos', [])),
            }
            # self.log_extra_listing_info(listing_data, property_details)
            return property_details
        else:
            print("No listing data found on this page.")
            return None

    def log_extra_listing_info(self, listing_data, property_details):
        # Print any additional fields not captured in property_details
        captured_fields = set([
                'token', 'adNumber', 'address', 'price', 'additionalDetails', 
                'metaData', 'propertyTax', 'houseCommittee', 'inProperty', 
                'furnitureInfo', 'dates', 'tags'
            ])
            
        additional_fields = {}
        for key, value in listing_data.items():
            if key not in captured_fields:
                additional_fields[key] = value
            
        if additional_fields:
            print(f"Additional fields found in listing {property_details['listing_id']}:")
            for key, value in additional_fields.items():
                print(f"  {key}: {value}")
            print()

    def extract_listing_links(self, listings):
        # 3. Create an empty list to hold the links
        all_listing_links = []

        # 4. Loop through each listing found
        for listing in listings:
                full_url = SCRAPER_CONFIG["base_url"] + listing['token']
                print(full_url)
                all_listing_links.append(full_url)

                return all_listing_links

    def print_listings(self, all_listings):
        print(f"Found {len(all_listings)} listings.\n---")
        for listing in all_listings:
                # Extracting data using .get() to avoid errors if a key is missing
            price = listing.get('price')
            address_info = listing.get('address', {})
            city = address_info.get('city', {}).get('text')
            street = address_info.get('street', {}).get('text')
                
            details = listing.get('additionalDetails', {})
            rooms = details.get('roomsCount')
            size = details.get('squareMeter')
                
            print(f"Price: ₪{price}")
            print(f"Address: {street}, {city}")
            print(f"Rooms: {rooms}, Size: {size} sqm")
            print("---")

    def check_listing_categories(self, feed):
        print("\n--- Listing Categories Found on This Page ---")
        all_listings_on_page = []
        if feed:
                        # Iterate through each category (e.g., 'feedItems', 'platinum') in the feed
            for category_name, listings in feed.items():
                            # We only care about categories that are non-empty lists
                if isinstance(listings, list) and listings:
                    print(f"-> Category '{category_name}': Found {len(listings)} listings.")
                                # Add the listings from this category to our main list
                    all_listings_on_page.extend(listings)

class Yad2MultiSearchScraper(Yad2Scraper):
    def __init__(self, search_configs=None, enable_notifications=True):
        # Initialize with base configuration
        super().__init__()
        self.search_configs = search_configs or SEARCH_CONFIGURATIONS
        
        # Initialize notification system
        self.enable_notifications = enable_notifications 
        self.notifier = None
        self.property_tracker = PropertyTracker(settings.database_path)
        
        # Track scraped listings to avoid duplicates
        self.scraped_listings = {}  # Cache for already scraped listings
        
        if self.enable_notifications:
            self._setup_notifier()
    
    def _setup_notifier(self):
        """Setup Telegram notifier if credentials are available"""
        try:
            if settings.telegram_bot_token and settings.telegram_chat_id:
                self.notifier = TelegramNotifier(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id
                )
                print("✅ Telegram notifier initialized successfully")
            else:
                print("⚠️ Telegram credentials not found - notifications disabled")
                self.enable_notifications = False
        except Exception as e:
            print(f"❌ Failed to initialize Telegram notifier: {e}")
            self.enable_notifications = False
    
    def _handle_notifications(self, combined_df):
        """Handle notifications for new and updated properties"""
        print(f"🔍 DEBUG: Checking notifications...")
        print(f"🔍 DEBUG: Notifier exists: {self.notifier is not None}")
        print(f"🔍 DEBUG: Enable notifications: {self.enable_notifications}")
        print(f"🔍 DEBUG: Total properties in DF: {len(combined_df)}")
        
        try:
            if not self.notifier:
                print("🔍 DEBUG: No notifier - returning early")
                return
            
            # Track new properties
            new_properties = []
            for _, property_data in combined_df.iterrows():
                property_id = property_data['listing_id']
                exists = self.property_tracker.property_exists(property_id)
                print(f"🔍 DEBUG: Property {property_id} exists in DB: {exists}")
                
                if not exists:
                    new_properties.append(property_data)
                    self.property_tracker.add_property(property_id, property_data.to_dict())
            
            print(f"🔍 DEBUG: Found {len(new_properties)} new properties")
            print(f"🔍 DEBUG: notify_on_new_properties setting: {getattr(settings, 'notify_on_new_properties', 'NOT_SET')}")
            
            # Send notifications for new properties only (no summary)
            if new_properties and settings.notify_on_new_properties:
                # Send individual notifications without summary
                successful_notifications = 0
                for property_data in new_properties:
                    message = self.notifier.format_property_message(property_data.to_dict())
                    if self.notifier.send_message(message):
                        successful_notifications += 1
                    
                    # Small delay between messages to avoid rate limiting
                    import time
                    time.sleep(1)
                
                print(f"📱 Sent {successful_notifications}/{len(new_properties)} notifications for new properties")
            else:
                print(f"📱 No new properties to notify about ({len(new_properties)} new properties found)")
                
        except Exception as e:
            print(f"❌ Error handling notifications: {e}")
            if settings.notify_on_error:
                self.notifier.send_error_notification(f"Notification error: {str(e)}")
    
    def run_multi_search(self):
        """Run scraping across multiple search configurations and combine results"""
        all_listings = []  # Collect all listings first
        
        try:
            # First pass: Collect all unique listings from all searches
            for i, config in enumerate(self.search_configs, 1):
                print(f"\n=== Fetching listings {i}/{len(self.search_configs)}: {config['name']} ===")
                
                try:
                    # Fetch listings for this configuration
                    listings = self.fetch_listings(config["params"])
                    
                    if listings:
                        # Add search config metadata to each listing
                        for listing in listings:
                            listing['search_config'] = config['name']
                        
                        all_listings.extend(listings)
                        print(f"✅ Found {len(listings)} listings for {config['name']}")
                    else:
                        print(f"⚠️ No listings found for {config['name']}")
                        
                except Exception as e:
                    print(f"❌ Error processing {config['name']}: {e}")
                    if self.enable_notifications and settings.notify_on_error:
                        self.notifier.send_error_notification(f"Error in search '{config['name']}': {str(e)}")
                    continue
                    
                # Add delay between searches to be respectful
                if i < len(self.search_configs):
                    print("Waiting between searches...")
                    time.sleep(3)
            
            # Deduplicate listings by token before scraping
            unique_listings = self._deduplicate_listings(all_listings)
            print(f"\n📊 Total listings found: {len(all_listings)}")
            print(f"📊 Unique listings to scrape: {len(unique_listings)}")
            print(f"📊 Duplicates avoided: {len(all_listings) - len(unique_listings)}")
            
            # Second pass: Scrape unique listings only
            if unique_listings:
                combined_df = self.scrape_listings_pages(unique_listings)
                
                if not combined_df.empty:
                    # Add timestamp
                    combined_df['search_timestamp'] = pd.Timestamp.now()
                    
                    # Check for new properties and send notifications
                    if self.enable_notifications:
                        self._handle_notifications(combined_df)
                    
                    self.print_search_summary_v2(all_listings, unique_listings, combined_df)
                    return combined_df
                else:
                    print("❌ No data scraped successfully")
                    return pd.DataFrame()
            else:
                print("❌ No unique listings to scrape")
                return pd.DataFrame()
                
        except Exception as e:
            error_msg = f"Critical error in multi-search: {str(e)}"
            print(f"❌ {error_msg}")
            if self.enable_notifications and settings.notify_on_error:
                self.notifier.send_error_notification(error_msg)
            raise
    
    def _deduplicate_listings(self, all_listings):
        """Remove duplicate listings based on token, keeping track of which searches found each property"""
        seen_tokens = {}
        unique_listings = []
        
        for listing in all_listings:
            token = listing.get('token')
            if token:
                if token not in seen_tokens:
                    # First time seeing this listing
                    listing['found_in_searches'] = [listing['search_config']]
                    seen_tokens[token] = listing
                    unique_listings.append(listing)
                else:
                    # Already seen this listing, just add the search config
                    seen_tokens[token]['found_in_searches'].append(listing['search_config'])
        
        return unique_listings
    
    def scrape_listings_pages(self, listings):
        """Override to handle the new listing structure with search metadata"""
        all_properties = []
        
        for listing in listings:
            listing_id = listing['token']
            
            # Check if we've already scraped this listing
            if listing_id in self.scraped_listings:
                print(f"📋 Using cached data for listing {listing_id}")
                cached_property = self.scraped_listings[listing_id].copy()
                # Update search metadata
                cached_property['found_in_searches'] = listing.get('found_in_searches', [listing.get('search_config', 'unknown')])
                all_properties.append(cached_property)
                continue
            
            # Scrape new listing
            full_url = SCRAPER_CONFIG["base_item_url"] + listing_id
            property_details = self.scrape_listing_page(full_url)
            
            if property_details:
                # Add search metadata
                property_details['found_in_searches'] = listing.get('found_in_searches', [listing.get('search_config', 'unknown')])
                
                # Cache the result
                self.scraped_listings[listing_id] = property_details.copy()
                all_properties.append(property_details)
            
            # Small delay between requests
            time.sleep(0.5)
        
        if all_properties: 
            df = pd.DataFrame(all_properties)
            return df
        
        return pd.DataFrame()
    
    def print_search_summary_v2(self, all_listings, unique_listings, combined_df):
        """Print improved summary of search results"""
        print("\n" + "="*60)
        print("SEARCH SUMMARY")
        print("="*60)
        
        # Count listings per search config
        search_counts = {}
        for listing in all_listings:
            config = listing.get('search_config', 'unknown')
            search_counts[config] = search_counts.get(config, 0) + 1
        
        for config_name, count in search_counts.items():
            print(f"{config_name}: {count} listings")
        
        print(f"\nTotal listings found: {len(all_listings)}")
        print(f"Unique listings scraped: {len(unique_listings)}")
        print(f"Duplicates avoided: {len(all_listings) - len(unique_listings)}")
        print(f"Successfully processed: {len(combined_df)}")
        
        # Show which searches had overlaps
        if len(combined_df) > 0:
            overlap_analysis = self._analyze_search_overlaps(combined_df)
            if overlap_analysis:
                print(f"\n🔄 Search overlaps found:")
                for overlap in overlap_analysis:
                    print(f"   {overlap}")
        
        print("="*60)
    
    def _analyze_search_overlaps(self, df):
        """Analyze which properties were found in multiple searches"""
        overlaps = []
        
        for _, row in df.iterrows():
            found_in = row.get('found_in_searches', [])
            if len(found_in) > 1:
                overlaps.append(f"Property {row['listing_id']} found in: {', '.join(found_in)}")
        
        return overlaps[:10]  # Return first 10 overlaps to avoid spam