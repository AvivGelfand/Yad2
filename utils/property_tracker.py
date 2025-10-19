import json
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Set

class PropertyTracker:
    def __init__(self, database_path: str = 'data/seen_properties.json'):
        """
        Initialize property tracker
        
        Args:
            database_path: Path to JSON file storing seen property IDs
        """
        self.database_path = database_path
        self.seen_properties = self._load_seen_properties()
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
    
    def _load_seen_properties(self) -> Set[str]:
        """Load previously seen property IDs from file"""
        if os.path.exists(self.database_path):
            try:
                with open(self.database_path, 'r') as f:
                    data = json.load(f)
                    return set(data.get('seen_ids', []))
            except (json.JSONDecodeError, FileNotFoundError):
                return set()
        return set()
    
    def _save_seen_properties(self):
        """Save seen property IDs to file"""
        data = {
            'seen_ids': list(self.seen_properties),
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.database_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_new_properties(self, current_properties: pd.DataFrame) -> pd.DataFrame:
        """
        Identify new properties that haven't been seen before
        
        Args:
            current_properties: DataFrame with current property listings
            
        Returns:
            DataFrame containing only new properties
        """
        if current_properties.empty:
            return current_properties
        
        # Filter out properties we've already seen
        new_mask = ~current_properties['listing_id'].isin(self.seen_properties)
        new_properties = current_properties[new_mask].copy()
        
        return new_properties
    
    def mark_properties_as_seen(self, properties: pd.DataFrame):
        """
        Mark properties as seen and save to database
        
        Args:
            properties: DataFrame containing properties to mark as seen
        """
        if not properties.empty:
            new_ids = set(properties['listing_id'].astype(str))
            self.seen_properties.update(new_ids)
            self._save_seen_properties()
    
    def get_stats(self) -> Dict:
        """Get statistics about tracked properties"""
        return {
            'total_seen': len(self.seen_properties),
            'database_path': self.database_path,
            'last_updated': self._get_last_updated()
        }
    
    def _get_last_updated(self) -> str:
        """Get last updated timestamp from database"""
        if os.path.exists(self.database_path):
            try:
                with open(self.database_path, 'r') as f:
                    data = json.load(f)
                    return data.get('last_updated', 'Unknown')
            except (json.JSONDecodeError, FileNotFoundError):
                return 'Unknown'
        return 'Never'
    
    def property_exists(self, property_id: str) -> bool:
        """
        Check if a property ID has been seen before
        
        Args:
            property_id: The property ID to check
            
        Returns:
            True if property has been seen before, False otherwise
        """
        return str(property_id) in self.seen_properties
    
    def add_property(self, property_id: str, property_data: Dict = None):
        """
        Add a property to the seen properties list
        
        Args:
            property_id: The property ID to add
            property_data: Optional property data (for future use)
        """
        self.seen_properties.add(str(property_id))
        self._save_seen_properties()