"""Madlan search configuration.

Unlike Yad2 (where we build query params), Madlan's search filters live in a
positional, underscore-delimited path/query DSL that is painful to reconstruct.
So we just take full search-page URLs — copy them straight from the browser after
setting your filters. Each entry is fetched, its embedded results parsed, and
(optionally) each listing enriched from its item page.

To add a search: set your filters on madlan.co.il, copy the address-bar URL,
paste it here with a short name.

Madlan's search feed pads results with NEARBY-city listings (a Herzliya search
also returns Ramat HaSharon / Ra'anana flats). The scraper drops these, keeping
only listings whose city matches the URL's area slug (e.g. הרצליה-ישראל). If the
slug can't be parsed for a search, add an explicit `"city_doc_id": "<slug>-ישראל"`
to that entry to force the filter.
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

# Fetch each listing's item page for full detail? MUST stay True: the search
# feed carries NO `amenities` object (elevator/secureRoom/miklat/balcony/AC are
# item-page-only), so feed-only rows report every amenity as null — which the
# Telegram notifier renders as "❌ No" (e.g. a real elevator shown as "no
# elevator"). Only the item page has amenities, so we always enrich.
# False would be faster/lower-block-risk but loses all amenity accuracy.
MADLAN_FETCH_DETAILS = True

# Upper bound on listings collected per search (the browser scrolls to load more
# past the ~15 the page embeds). Override per-run with the MADLAN_MAX_RESULTS env.
import os as _os
MADLAN_MAX_RESULTS = int(_os.getenv("MADLAN_MAX_RESULTS", "200"))
