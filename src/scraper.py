import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

# Configurable parameters for the scraper
SCRAPER_CONFIG = {
    "url": "https://www.yad2.co.il/realestate/rent",
    "base_url": "https://www.yad2.co.il",
    "headers": {},
    "params": {
        "minPrice": "3000",
        "maxPrice": "10000",
        "minRooms": "3",
        "maxRooms": "4.5",
        "imageOnly": "1",
        "priceOnly": "1",
        "elevator": "1",
        "balcony": "1",
        # "shelter": "1",
        "renovated": "1",
        "topArea": "19",
        "area": "18",
        "city": "6400",
        "zoom": "12"
    }
}


class Yad2Scraper:
    def __init__(self, url=None, headers=None, params=None):
        self.url = url or SCRAPER_CONFIG["url"]
        self.headers = headers if headers is not None else SCRAPER_CONFIG["headers"]
        self.params = params if params is not None else SCRAPER_CONFIG["params"]

    def fetch_listings(self):
        all_listings = []
        current_page = 1
        total_pages = 1  # We'll update this after the first request

        while current_page <= total_pages:
            print(f"Fetching page {current_page}...")
            self.params['page'] = current_page
            
            try:
                # Make the web request for the current page
                response = requests.get(self.url, params=self.params, headers=self.headers)
                response.raise_for_status()  # This will raise an error for bad responses (4xx or 5xx)

                # --- Parse the response ---
                soup = BeautifulSoup(response.text, 'html.parser')
                # 2. Find the script tag containing the JSON data

                script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
                
                if not script_tag:
                    print(f"Could not find data on page {current_page}. Stopping.")
                    break

                if script_tag:
                    data = json.loads(script_tag.string)

                    # Navigate through the nested dictionary to find the listings
                    feed = data.get('props', {}).get('pageProps', {}).get('feed', {})
                    
                    self.check_listing_categories(feed)
                    
                    # The listings are in several lists, so we combine them
                    all_listings = []
                    # Regular listings
                    all_listings.extend(feed.get('private', [])) 
                    # Promoted listings
                    all_listings.extend(feed.get('platinum', []))  
                    all_listings.extend(feed.get('agency', []))  
                    
                    # 5. Loop through the listings and print the details
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
                
                current_page += 1
                
                # Add a delay to be respectful to the website's servers
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                print(f"An error occurred during the request: {e}")
                break
            except json.JSONDecodeError:
                print(f"Failed to parse JSON on page {current_page}. Content might be invalid.")
                break
            
        
        ##### 
        # response = requests.get(self.url,
                                #  headers=self.headers,
                                #  params=self.params)
        # response.raise_for_status()
        
        # soup = BeautifulSoup(response.text,'html.parser')
        # script_tag = soup.find('script', {'id': '__NEXT_DATA__'})   
        
        # 3. Load the content of the script tag as a JSON object
        if script_tag:
            data = json.loads(script_tag.string)

            # 4. Navigate through the nested dictionary to find the listings
            feed = data.get('props', {}).get('pageProps', {}).get('feed', {})
            
            # The listings are in several lists, so we combine them
            all_listings = []
            # Regular listings
            all_listings.extend(feed.get('private', [])) 
            # Promoted listings
            all_listings.extend(feed.get('platinum', []))  
            all_listings.extend(feed.get('agency', []))  
            
            # 5. Loop through the listings and print the details
            self.print_listings(all_listings)



        # ---
        # 2. Find all the <li> elements that are individual listings
        # We use the 'data-nagish' attribute as it's a consistent identifier.
        # listings = soup.find_all('li', attrs={'data-nagish': 'feed-item-list-box'})

        # 3. Create an empty list to hold the links
        all_listing_links = []

        # 4. Loop through each listing found
        for listing in all_listings:
            # Find the <a> tag with the specific class that holds the link
            link_tag = listing.find('a', class_='item-layout_itemLink__CZZ7w')
            
            # Check if the tag and its href attribute exist
            if link_tag and 'href' in link_tag.attrs:
                # Get the relative URL from the href attribute
                relative_url = link_tag['href']
                parsed = urlparse(relative_url)
                result = parsed.path   # keeps only the path part, drops query/fragment

                # Construct the full URL and add it to our list
                full_url = SCRAPER_CONFIG["base_url"] + result
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


def main():
    # You can update SCRAPER_CONFIG here before creating the scraper
    # Example: SCRAPER_CONFIG["params"]["city"] = "tel-aviv"
    scraper = Yad2Scraper()
    listings = scraper.fetch_listings()
    for listing in listings:
        print(listing)

    print(f"\nScraping complete! ✨")
    print(f"Found a total of {len(listings)} listings across all pages.")



if __name__ == "__main__":
    main()
