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
            # Create a dictionary to hold the extracted info for one listing
            property_details = {
                'listing_id': listing_data.get('token'),
                'ad_number': listing_data.get('adNumber'),
                'city': listing_data.get('address', {}).get('city', {}).get('text'),
                'neighborhood': listing_data.get('address', {}).get('neighborhood', {}).get('text'),
                'street': listing_data.get('address', {}).get('street', {}).get('text'),
                'price_ils': listing_data.get('price'),
                'property_type': listing_data.get('additionalDetails', {}).get('property', {}).get('text'),
                'rooms': listing_data.get('additionalDetails', {}).get('roomsCount'),
                'floor': listing_data.get('address', {}).get('house', {}).get('floor'),
                'elevator': listing_data.get('inProperty', {}).get('includeElevator'),
                'total_floors': listing_data.get('additionalDetails', {}).get('buildingTopFloor'),
                'area_sqm': listing_data.get('additionalDetails', {}).get('squareMeter'),
                'condition': listing_data.get('additionalDetails', {}).get('propertyCondition', {}).get('text'),
                'entry_date': listing_data.get('additionalDetails', {}).get('entranceDate', '').split('T')[0],
                'description': listing_data.get('metaData', {}).get('description'),
                'search_text': listing_data.get('metaData', {}).get('searchText'),
                'isLongTermContract': listing_data.get('additionalDetails', {}).get('isLongTermContract'),
                # Calculate monthly arnona (it's given for two months)
                'monthly_arnona_ils': listing_data.get('propertyTax', 0) / 2 if listing_data.get('propertyTax') and listing_data.get('propertyTax') > 0 else None,
                'monthly_vaad_ils': listing_data.get('houseCommittee'),
                'parking': listing_data.get('inProperty', {}).get('includeParking'),
                'balcony': listing_data.get('inProperty', {}).get('includeBalcony'),
                'mamad': listing_data.get('inProperty', {}).get('includeSecurityRoom'),
                'AC': listing_data.get('inProperty', {}).get('includeAirconditioner'),
                'Boiler': listing_data.get('inProperty', {}).get('includeBoiler'),
                'renovated': listing_data.get('inProperty', {}).get('isRenovated'),
                'furniture': listing_data.get('furnitureInfo', ''),
                'pets': listing_data.get('inProperty', {}).get('isPetsAllowed'),

                'created_at': listing_data.get('dates', {}).get('createdAt'),
                'updated_at': listing_data.get('dates', {}).get('updatedAt'),
                'latitude': listing_data.get('address', {}).get('coords', {}).get('lat'),
                'longitude': listing_data.get('address', {}).get('coords', {}).get('lon'),
                'tags': listing_data.get('tags', []),

                'url': listing_url,
                'image_count': len(listing_data.get('metaData', {}).get('images', [])),
                'images': listing_data.get('metaData', {}).get('images', []),
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
    def __init__(self, search_configs=None):
        # Initialize with base configuration
        super().__init__()
        self.search_configs = search_configs or SEARCH_CONFIGURATIONS
        
    def run_multi_search(self):
        """Run scraping across multiple search configurations and combine results"""
        all_dataframes = []
        
        for i, config in enumerate(self.search_configs, 1):
            print(f"\n=== Starting search {i}/{len(self.search_configs)}: {config['name']} ===")
            
            # Update parameters for this search
            # self.params = {**SCRAPER_CONFIG["params"], **config["params"]}
            
            try:
                # Fetch listings for this configuration
                listings = self.fetch_listings(config["params"])
                
                if listings:
                    # Scrape detailed pages
                    df = self.scrape_listings_pages(listings)
                    
                    if not df.empty:
                        # Add search configuration metadata
                        df['search_config'] = config['name']
                        df['search_timestamp'] = pd.Timestamp.now()
                        all_dataframes.append(df)
                        print(f"✅ Found {len(df)} properties for {config['name']}")
                    else:
                        print(f"⚠️ No properties found for {config['name']}")
                else:
                    print(f"⚠️ No listings found for {config['name']}")
                    
            except Exception as e:
                print(f"❌ Error processing {config['name']}: {e}")
                continue
                
            # Add delay between searches to be respectful
            if i < len(self.search_configs):
                print("Waiting between searches...")
                time.sleep(3)
        
        # Combine all results
        if all_dataframes:
            combined_df = self.combine_and_deduplicate(all_dataframes)
            self.print_search_summary(all_dataframes, combined_df)
            return combined_df
        else:
            print("❌ No data found across all searches")
            return pd.DataFrame()
    
    def print_search_summary(self, dataframes, combined_df):
        """Print summary of search results"""
        print(f"\n=== SEARCH SUMMARY ===")
        total_before = sum(len(df) for df in dataframes)
        total_after = len(combined_df)
        
        print(f"Total listings found: {total_before}")
        print(f"Unique listings after deduplication: {total_after}")
        print(f"Duplicates removed: {total_before - total_after}")
        
        # Price range summary
        if not combined_df.empty:
            min_price = combined_df['price_ils'].min()
            max_price = combined_df['price_ils'].max()
            avg_price = combined_df['price_ils'].mean()
            print(f"Price range: ₪{min_price:,.0f} - ₪{max_price:,.0f} (avg: ₪{avg_price:,.0f})")
        
        print(f"======================\n")

    def combine_and_deduplicate(self, dataframes):
        """Combine multiple dataframes and remove duplicates based on listing_id"""
        if not dataframes:
            return pd.DataFrame()
        
        # Combine all dataframes
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Remove duplicates based on listing_id (keep first occurrence)
        # This preserves the search order priority
        combined_df = combined_df.drop_duplicates(subset=['listing_id'], keep='first')
        
        # Reset index after deduplication
        combined_df = combined_df.reset_index(drop=True)
        
        return combined_df