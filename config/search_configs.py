SEARCH_CONFIGURATIONS = [
    {
        "name": "Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "8000",
            "priceOnly": "1",
            "elevator": "1",
            "balcony": "1",
            "renovated": "1"
        }
    },
    {
        "name": "Not Renovated",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "7000",
            "imageOnly": "1",
            "priceOnly": "1",
            "elevator": "1",
            "balcony": "1",
        }
    },
        {
        "name": "No Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "7000",
            "priceOnly": "1",
            "balcony": "1",
            "minFloor": "0",
            "maxFloor": "1",
            "renovated": "1"
        }
        },
            {
        "name": "5 Rooms No Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "5",
            "minPrice": "5000",
            "maxPrice": "7300",
            "imageOnly": "1",
            "priceOnly": "1",
            "balcony": "1",
            "minFloor": "0",
            "maxFloor": "1",
            "renovated": "1"
        }
    },
        {
        "name": "5 Rooms with Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "5",
            "minPrice": "5000",
            "maxPrice": "7500",
            "imageOnly": "1",
            "priceOnly": "1",
            "balcony": "1",
            "renovated": "1",
            "elevator": "1",
        }
    },
            {
        "name": "No Balcony with Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "5",
            "minPrice": "4500",
            "maxPrice": "7000",
            "imageOnly": "1",
            "priceOnly": "1",
            "renovated": "1",
            "elevator": "1",
        }
    },
]


# Configurable parameters for the scraper.
# The rental search URL now carries the region as a PATH SLUG
# (center-and-sharon = topArea 19 / area 18), and `area`+`city` as query params.
# Change region_slug + base_params together if you search a different region.
SCRAPER_CONFIG = {
    "url": "https://www.yad2.co.il/realestate/rent/center-and-sharon",
    "base_item_url": "https://www.yad2.co.il/realestate/item/",
    # Params merged into every search (the "where"); per-config params add the filters.
    "base_params": {"area": "18", "city": "6400"},
}