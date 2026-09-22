"""Madlan search configuration.

Unlike Yad2 (where we build query params), Madlan's search filters live in a
positional, underscore-delimited path/query DSL that is painful to reconstruct.
So we just take full search-page URLs — copy them straight from the browser after
setting your filters. Each entry is fetched, its embedded results parsed, and
(optionally) each listing enriched from its item page.

To add a search: set your filters on madlan.co.il, copy the address-bar URL,
paste it here with a short name.
"""

MADLAN_SEARCHES = [
    {
        "name": "Herzliya rent 5000-8500, 3-4.5 rooms, amenities",
        # rent ₪5000–8500, 3–4.5 rooms, secureRoom/mamak/miklat/balcony/elevator
        "url": ("https://www.madlan.co.il/for-rent/%D7%94%D7%A8%D7%A6%D7%9C%D7%99%D7%94-"
                "%D7%99%D7%A9%D7%A8%D7%90%D7%9C?filters=_5000-8500_3-4.5____secureRoom"
                "%2Cmamak%2Cmiklat%2Cbalcony%2Celevator_____0-10000_______search-filter-top-bar"),
    },
]

# Fetch each listing's item page for full detail (description, all amenities)?
# False = parse only the search feed (price/rooms/area/coords/address/images) —
# faster and lower block-risk; enough for dedup and a listing row. When the
# search is already amenity-filtered, the feed rows already satisfy those.
MADLAN_FETCH_DETAILS = False

# Upper bound on listings collected per search (the browser scrolls to load more
# past the ~15 the page embeds). Override per-run with the MADLAN_MAX_RESULTS env.
import os as _os
MADLAN_MAX_RESULTS = int(_os.getenv("MADLAN_MAX_RESULTS", "200"))
