from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Property:
    """Data model for a real estate property"""
    
    # Core identification
    listing_id: Optional[str] = None
    ad_number: Optional[str] = None
    
    # Location details
    city: Optional[str] = None
    neighborhood: Optional[str] = None
    street: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Pricing
    price_ils: Optional[int] = None
    monthly_arnona_ils: Optional[float] = None
    monthly_vaad_ils: Optional[int] = None
    
    # Property details
    property_type: Optional[str] = None
    rooms: Optional[float] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    area_sqm: Optional[int] = None
    entry_date: Optional[str] = None
    
    # Features
    has_elevator: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_balcony: Optional[bool] = None
    has_mamad: Optional[bool] = None
    is_renovated: Optional[bool] = None
    
    # Metadata
    description: Optional[str] = None
    image_count: Optional[int] = None
    created_at: Optional[str] = None
    last_updated: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert the property to a dictionary"""
        return {
            'listing_id': self.listing_id,
            'ad_number': self.ad_number,
            'city': self.city,
            'neighborhood': self.neighborhood,
            'street': self.street,
            'price_ils': self.price_ils,
            'property_type': self.property_type,
            'rooms': self.rooms,
            'floor': self.floor,
            'total_floors': self.total_floors,
            'area_sqm': self.area_sqm,
            'entry_date': self.entry_date,
            'description': self.description,
            'monthly_arnona_ils': self.monthly_arnona_ils,
            'monthly_vaad_ils': self.monthly_vaad_ils,
            'has_elevator': self.has_elevator,
            'has_parking': self.has_parking,
            'has_balcony': self.has_balcony,
            'has_mamad': self.has_mamad,
            'is_renovated': self.is_renovated,
            'created_at': self.created_at,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'image_count': self.image_count,
            'last_updated': self.last_updated or datetime.now().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Property':
        """Create a Property instance from a dictionary"""
        return cls(
            listing_id=data.get('listing_id'),
            ad_number=data.get('ad_number'),
            city=data.get('city'),
            neighborhood=data.get('neighborhood'),
            street=data.get('street'),
            price_ils=data.get('price_ils'),
            property_type=data.get('property_type'),
            rooms=data.get('rooms'),
            floor=data.get('floor'),
            total_floors=data.get('total_floors'),
            area_sqm=data.get('area_sqm'),
            entry_date=data.get('entry_date'),
            description=data.get('description'),
            monthly_arnona_ils=data.get('monthly_arnona_ils'),
            monthly_vaad_ils=data.get('monthly_vaad_ils'),
            has_elevator=data.get('has_elevator'),
            has_parking=data.get('has_parking'),
            has_balcony=data.get('has_balcony'),
            has_mamad=data.get('has_mamad'),
            is_renovated=data.get('is_renovated'),
            created_at=data.get('created_at'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            image_count=data.get('image_count'),
            last_updated=data.get('last_updated')
        )