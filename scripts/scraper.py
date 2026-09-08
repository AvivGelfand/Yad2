import pandas as pd
from urllib.parse import urlencode
import time
import sys
import os
# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))  # for sibling modules yad2_fetch / yad2_parse

from config.search_configs import SEARCH_CONFIGURATIONS, SCRAPER_CONFIG
from config.settings import settings
from notifications.telegram_notifier import TelegramNotifier
from utils.property_tracker import PropertyTracker
import yad2_fetch
import yad2_parse as yp


class Yad2Blocked(Exception):
    """Raised when Yad2's anti-bot WAF blocks the request (403 / challenge).

    Surfaced instead of silently returning 0 listings so the run fails loudly
    and an error notification is sent. Almost always means the run is on a
    datacenter/CI IP — use a residential IP."""



class Yad2Scraper:
    def __init__(self, url=None):
        self.url = url or SCRAPER_CONFIG["url"]
        # Long-lived browser session, set by run_multi_search for the whole run.
        self._session = None

    def _fetch_html(self, url):
        """Fetch a URL through the browser engine. Uses the shared session if
        one is active (fast), else spins up a one-shot browser."""
        if self._session is not None:
            return self._session.fetch(url)
        return yad2_fetch.fetch_page(url)

    def fetch_listings(self, params=None):
        all_listings = []
        # Merge the region/area/city "where" with this search's filters.
        search_params = {**SCRAPER_CONFIG.get("base_params", {}), **(params or {})}

        print(f"Fetching listings with params: {search_params}")

        for current_page in range(1, 6):  # cap at 5 pages/search
            print(f"Fetching page {current_page}...")
            url = self.url + "?" + urlencode({**search_params, "page": current_page})

            try:
                status, html = self._fetch_html(url)
            except Exception as e:
                print(f"An error occurred during the request: {e}")
                break

            if yp.is_blocked(html, status):
                raise Yad2Blocked(
                    f"Yad2 anti-bot block on page {current_page}. "
                    f"{yp.page_summary(html, status)}. "
                    f"Run from a residential IP (datacenter/CI IPs are blocked)."
                )

            next_data = yp.extract_next_data(html)
            page_listings = yp.extract_feed_listings(next_data) if next_data else []

            if not page_listings:
                print(f"No listings found on page {current_page}. Stopping.")
                break

            all_listings.extend(page_listings)
            print(f"Found {len(page_listings)} listings on page {current_page}")
            time.sleep(1)  # be respectful to the server

        print(f"Total listings found: {len(all_listings)}")
        return all_listings
    
    def scrape_listings_pages(self, listings):
        all_properties = []
        failed_listings = []

        for listing in listings:
            try:
                listing_id = listing.get('token', 'unknown')
                full_url = SCRAPER_CONFIG["base_item_url"] + listing_id
                property_details = self.scrape_listing_page(full_url)

                if property_details:
                    all_properties.append(property_details)
                else:
                    failed_listings.append(listing_id)
                    print(f"⚠️ Skipping listing {listing_id} - failed to scrape")

            except Exception as e:
                print(f"⚠️ Unexpected error processing listing {listing.get('token', 'unknown')}: {e}")
                failed_listings.append(listing.get('token', 'unknown'))
                continue

        # Print summary of failures
        if failed_listings:
            print(f"\n⚠️ Failed to scrape {len(failed_listings)} listings: {', '.join(failed_listings)}")

        if all_properties:
            df = pd.DataFrame(all_properties)
            # print(df.head())
            return df

        return pd.DataFrame()

    def scrape_listing_page(self, listing_url):
        print(f"Scraping individual listing page: {listing_url}")
        try:
            status, html = self._fetch_html(listing_url)
        except Exception as e:
            print(f"⚠️ Request error scraping {listing_url}: {e}")
            return None

        if yp.is_blocked(html, status):
            raise Yad2Blocked(
                f"Yad2 anti-bot block on item {listing_url}. {yp.page_summary(html, status)}"
            )

        next_data = yp.extract_next_data(html)
        listing_data = yp.extract_item_detail(next_data) if next_data else None
        if not listing_data:
            print(f"⚠️ Could not find item data for {listing_url}")
            return None

        return yp.parse_item_detail(listing_data, link=listing_url)


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
        try:
            if not self.notifier:
                return

            # Track new properties
            new_properties = []
            for _, property_data in combined_df.iterrows():
                property_id = property_data['listing_id']
                if not self.property_tracker.property_exists(property_id):
                    new_properties.append(property_data)
                    self.property_tracker.add_property(property_id, property_data.to_dict())

            print(f"📋 {len(new_properties)} new / {len(combined_df)} total properties")

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
    
    def _notify_error(self, message):
        """Send an error notification if notifications are configured."""
        if self.enable_notifications and self.notifier and settings.notify_on_error:
            try:
                self.notifier.send_error_notification(message)
            except Exception as notif_error:
                print(f"⚠️ Failed to send error notification: {notif_error}")

    def run_multi_search(self):
        """Run scraping across multiple search configurations and combine results"""
        all_listings = []  # Collect all listings first

        try:
            # One browser for the whole run — launching per request is too slow.
            with yad2_fetch.BrowserSession() as session:
                self._session = session
                print(f"🌐 Browser engine: {yad2_fetch.ENGINE}")

                # First pass: Collect all listings from all searches
                for i, config in enumerate(self.search_configs, 1):
                    print(f"\n=== Fetching listings {i}/{len(self.search_configs)}: {config['name']} ===")

                    try:
                        listings = self.fetch_listings(config["params"])
                    except Yad2Blocked as e:
                        # Every config would be blocked identically — abort loudly.
                        print(f"❌ {e}")
                        self._notify_error(str(e))
                        break
                    except Exception as e:
                        print(f"❌ Error processing {config['name']}: {e}")
                        self._notify_error(f"Error in search '{config['name']}': {str(e)}")
                        continue

                    if listings:
                        for listing in listings:
                            listing['search_config'] = config['name']
                        all_listings.extend(listings)
                        print(f"✅ Found {len(listings)} listings for {config['name']}")
                    else:
                        print(f"⚠️ No listings found for {config['name']}")

                    # Add delay between searches to be respectful
                    if i < len(self.search_configs):
                        print("Waiting between searches...")
                        time.sleep(3)

                # Deduplicate listings by token before scraping
                unique_listings = self._deduplicate_listings(all_listings)
                print(f"\n📊 Total listings found: {len(all_listings)}")
                print(f"📊 Unique listings to scrape: {len(unique_listings)}")
                print(f"📊 Duplicates avoided: {len(all_listings) - len(unique_listings)}")

                # Second pass: Scrape unique listings only (still inside the session)
                if not unique_listings:
                    print("❌ No unique listings to scrape")
                    return pd.DataFrame()

                combined_df = self.scrape_listings_pages(unique_listings)

            if not combined_df.empty:
                combined_df['search_timestamp'] = pd.Timestamp.now()
                if self.enable_notifications:
                    self._handle_notifications(combined_df)
                self.print_search_summary_v2(all_listings, unique_listings, combined_df)
                return combined_df
            else:
                print("❌ No data scraped successfully")
                return pd.DataFrame()

        except Yad2Blocked as e:
            error_msg = f"Yad2 blocked during item scraping: {e}"
            print(f"❌ {error_msg}")
            self._notify_error(error_msg)
            return pd.DataFrame()
        except Exception as e:
            error_msg = f"Critical error in multi-search: {str(e)}"
            print(f"❌ {error_msg}")
            self._notify_error(error_msg)
            # Return empty DataFrame instead of raising to allow the process to complete
            return pd.DataFrame()
        finally:
            self._session = None
    
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
                    # Already seen — record the search config once (no repeats
                    # when the same listing appears on multiple pages of a search)
                    cfg = listing['search_config']
                    if cfg not in seen_tokens[token]['found_in_searches']:
                        seen_tokens[token]['found_in_searches'].append(cfg)
        
        return unique_listings
    
    def scrape_listings_pages(self, listings):
        """Override to handle the new listing structure with search metadata"""
        all_properties = []
        failed_listings = []

        for listing in listings:
            try:
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
                else:
                    failed_listings.append(listing_id)
                    print(f"⚠️ Skipping listing {listing_id} - failed to scrape")

            except Yad2Blocked:
                # A block is systemic, not a per-listing glitch — surface it.
                raise
            except Exception as e:
                print(f"⚠️ Unexpected error processing listing {listing.get('token', 'unknown')}: {e}")
                failed_listings.append(listing.get('token', 'unknown'))
                continue

            # Small delay between requests
            time.sleep(0.5)

        # Print summary of failures
        if failed_listings:
            print(f"\n⚠️ Failed to scrape {len(failed_listings)} listings: {', '.join(failed_listings)}")
        
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