# When True, results are filtered to apartments that have a protected space —
# ממ״ד (mamad), a building shelter/מקלט, or ממ״ק (mamak). Yad2's search feed
# carries no safe-room data (only each listing's detail page does), so this is
# applied client-side after the detail scrape, in scraper.run_multi_search.
REQUIRE_SAFE_ROOM = True

SEARCH_CONFIGURATIONS = [
            {
        "name": "most general search",
        "params": {
            "city": "6400",
            "minRooms": "3",
            "maxRooms": "4.5",
            "minPrice": "4500",
            "maxPrice": "8500",
            # "imageOnly": "1",
            "priceOnly": "1",
            # "renovated": "1",
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