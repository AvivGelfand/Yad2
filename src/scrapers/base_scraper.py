import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Any, Optional

from ..models.property import Property


class BaseScraper:
    """Base scraper class with common functionality"""
    
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None, 
                 request_delay: float = 1.0):
        self.base_url = base_url
        self.headers = headers or {}
        self.request_delay = request_delay
        self.logger = logging.getLogger(__name__)
        
    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request with error handling"""
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            time.sleep(self.request_delay)  # Be respectful to servers
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for URL {url}: {str(e)}")
            raise
    
    def _parse_json_from_script(self, soup: BeautifulSoup, script_id: str) -> Optional[Dict]:
        """Extract JSON data from script tag"""
        try:
            script_tag = soup.find('script', {'id': script_id})
            if script_tag and script_tag.string:
                return json.loads(script_tag.string)
        except (AttributeError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to parse JSON from script tag: {str(e)}")
        return None