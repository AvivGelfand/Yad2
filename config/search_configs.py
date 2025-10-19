SEARCH_CONFIGURATIONS = [
    {
        "name": "Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "8500",
            "imageOnly": "1",
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
            "maxPrice": "6500",
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
            "imageOnly": "1",
            "priceOnly": "1",
            "balcony": "1",
            "minFloor": "0",
            "maxFloor": "2",
            "renovated": "1"
        }
        },
            {
        "name": "5 Rooms No Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "5",
            "minPrice": "5500",
            "maxPrice": "7500",
            "imageOnly": "1",
            "priceOnly": "1",
            "balcony": "1",
            "minFloor": "0",
            "maxFloor": "2",
            "renovated": "1"
        }
    },
        {
        "name": "5 Rooms with Elevator",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "5",
            "minPrice": "5500",
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
            "minPrice": "5000",
            "maxPrice": "7000",
            "imageOnly": "1",
            "priceOnly": "1",
            "renovated": "1",
            "elevator": "1",
        }
    },
]


# Configurable parameters for the scraper
SCRAPER_CONFIG = {
    "url": "https://www.yad2.co.il/realestate/rent",
    "base_url": "https://www.yad2.co.il",
    "base_item_url": "https://www.yad2.co.il/realestate/item/",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0"
    }, 
}

params = { "params": {
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
    }}