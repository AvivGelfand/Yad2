import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import logging
from typing import List, Dict, Any, Optional

from .base_scraper import BaseScraper
from ..models.property import Property
from config.settings import settings


class Yad2Scraper(BaseScraper):
    """Specialized scraper for Yad2 real estate listings"""
    
    def __init__(self, url: Optional[str] = None, headers: Optional[Dict[str, str]] = None, 
                 params: Optional[Dict[str, str]] = None):
        super().__init__(
            base_url=settings.scraper.base_url,
            headers=headers or settings.scraper.headers,
            request_delay=settings.scraper.request_delay
        )
        
        self.url = url or settings.scraper.url
        self.base_item_url = settings.scraper.base_item_url
        self.params = params or self._get_default_params()
        
    def _get_default_params(self) -> Dict[str, str]:
        """Get default search parameters"""
        return {
            "minPrice": "3000",
            "maxPrice": "10000",
            "minRooms": "3",
            "maxRooms": "4.5",
            "imageOnly": "1",
            "priceOnly": "1",
            "elevator": "1",
            "balcony": "1",
            "renovated": "1",
            "topArea": "19",
            "area": "18",
            "city": "6400",
            "zoom": "12"
        }

    def fetch_listings(self) -> List[Dict[str, Any]]:
        """Fetch all listings from multiple pages"""
        all_listings = []
        current_page = 1
        max_pages = 10  # Safety limit
        
        while current_page <= max_pages:
            self.logger.info(f"Fetching page {current_page}...")
            self.params['page'] = current_page
            
            try:
                response = self._make_request(self.url, self.params)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse JSON data from script tag
                data = self._parse_json_from_script(soup, '__NEXT_DATA__')
                if not data:
                    self.logger.warning(f"No data found on page {current_page}")
                    break
                
                # Extract listings from the feed
                feed = data.get('props', {}).get('pageProps', {}).get('feed', {})
                page_listings = self._extract_listings_from_feed(feed)
                
                if not page_listings:
                    self.logger.info(f"No more listings found. Stopping at page {current_page}")
                    break
                
                all_listings.extend(page_listings)
                self.logger.info(f"Found {len(page_listings)} listings on page {current_page}")
                
                current_page += 1
                
            except Exception as e:
                self.logger.error(f"Error on page {current_page}: {str(e)}")
                break
        
        self.logger.info(f"Total listings fetched: {len(all_listings)}")
        return all_listings
    
    def _extract_listings_from_feed(self, feed: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract listings from the feed data"""
        all_listings = []
        
        # Combine listings from different categories
        categories = ['private', 'platinum', 'agency']
        for category in categories:
            listings = feed.get(category, [])
            if listings:
                all_listings.extend(listings)
                self.logger.debug(f"Found {len(listings)} listings in '{category}' category")
        
        return all_listings
    
    def scrape_detailed_listings(self, listings: List[Dict[str, Any]]) -> pd.DataFrame:
        """Scrape detailed information for each listing"""
        properties = []
        
        for i, listing in enumerate(listings[:10], 1): #TODO:remove limit
            self.logger.info(f"Scraping detailed info for listing {i}/{len(listings)}")
            
            try:
                property_details = self._scrape_listing_details(listing)
                if property_details:
                    properties.append(property_details.to_dict())
            except Exception as e:
                self.logger.error(f"Error scraping listing {listing.get('token', 'unknown')}: {str(e)}")
                continue
        
        if properties:
            df = pd.DataFrame(properties)
            self.logger.info(f"Successfully scraped {len(properties)} detailed listings")
            return df
        else:
            self.logger.warning("No detailed listings were scraped")
            return pd.DataFrame()
    
    def _scrape_listing_details(self, listing: Dict[str, Any]) -> Optional[Property]:
        """Scrape detailed information for a single listing"""
        token = listing.get('token')
        if not token:
            return None
        
        listing_url = f"{self.base_item_url}{token}"
        
        try:
            response = self._make_request(listing_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse JSON data
            data = self._parse_json_from_script(soup, '__NEXT_DATA__')
            if not data:
                return None
            
            # Navigate to listing data
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
            listing_data = None
            
            # Find the listing data in queries
            for query in queries:
                if query.get('state', {}).get('data', {}).get('token') == token:
                    listing_data = query['state']['data']
                    break
            
            if not listing_data:
                self.logger.warning(f"No detailed data found for listing {token}")
                return None
            
            return self._parse_property_data(listing_data)
            
        except Exception as e:
            self.logger.error(f"Error scraping details for {token}: {str(e)}")
            return None
    
    def _parse_property_data(self, listing_data: Dict[str, Any]) -> Property:
        """Parse listing data into Property object"""
        return Property(
            listing_id=listing_data.get('token'),
            ad_number=listing_data.get('adNumber'),
            city=listing_data.get('address', {}).get('city', {}).get('text'),
            neighborhood=listing_data.get('address', {}).get('neighborhood', {}).get('text'),
            street=listing_data.get('address', {}).get('street', {}).get('text'),
            price_ils=listing_data.get('price'),
            property_type=listing_data.get('additionalDetails', {}).get('property', {}).get('text'),
            rooms=listing_data.get('additionalDetails', {}).get('roomsCount'),
            floor=listing_data.get('address', {}).get('house', {}).get('floor'),
            total_floors=listing_data.get('additionalDetails', {}).get('buildingTopFloor'),
            area_sqm=listing_data.get('additionalDetails', {}).get('squareMeter'),
            entry_date=listing_data.get('additionalDetails', {}).get('entranceDate', '').split('T')[0] if listing_data.get('additionalDetails', {}).get('entranceDate') else None,
            description=listing_data.get('metaData', {}).get('description'),
            monthly_arnona_ils=listing_data.get('propertyTax', 0) / 2 if listing_data.get('propertyTax') and listing_data.get('propertyTax') > 0 else None,
            monthly_vaad_ils=listing_data.get('houseCommittee'),
            has_elevator=listing_data.get('inProperty', {}).get('includeElevator'),
            has_parking=listing_data.get('inProperty', {}).get('includeParking'),
            has_balcony=listing_data.get('inProperty', {}).get('includeBalcony'),
            has_mamad=listing_data.get('inProperty', {}).get('includeSecurityRoom'),
            is_renovated=listing_data.get('inProperty', {}).get('isRenovated'),
            created_at=listing_data.get('dates', {}).get('createdAt'),
            latitude=listing_data.get('address', {}).get('coords', {}).get('lat'),
            longitude=listing_data.get('address', {}).get('coords', {}).get('lon'),
            image_count=len(listing_data.get('metaData', {}).get('images', []))
        )
    
    def get_basic_listings_dataframe(self, listings: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert basic listing data to DataFrame without detailed scraping"""
        properties = []
        
        for listing in listings:
            try:
                property_data = {
                    'listing_id': listing.get('token'),
                    'price_ils': listing.get('price'),
                    'city': listing.get('address', {}).get('city', {}).get('text'),
                    'neighborhood': listing.get('address', {}).get('neighborhood', {}).get('text'),
                    'street': listing.get('address', {}).get('street', {}).get('text'),
                    'rooms': listing.get('additionalDetails', {}).get('roomsCount'),
                    'area_sqm': listing.get('additionalDetails', {}).get('squareMeter'),
                    'property_type': listing.get('additionalDetails', {}).get('property', {}).get('text'),
                    'created_at': listing.get('dates', {}).get('createdAt')
                }
                properties.append(property_data)
            except Exception as e:
                self.logger.error(f"Error parsing basic listing data: {str(e)}")
                continue
        
        return pd.DataFrame(properties)