"""Engine-agnostic parsing for Yad2 rental data.

This module knows NOTHING about how the page/JSON was fetched (requests,
Scrapling, Scrapy, Playwright, ...). It only turns raw HTML or gateway JSON
into the listing dicts the rest of the project already expects.

Two data sources are supported, both current as of 2026:
  * The rendered search page embeds a <script id="__NEXT_DATA__"> blob; the
    feed now lives at props.pageProps.dehydratedState.queries[].state.data
    (NOT the old props.pageProps.feed).
  * The JSON gateway API gw.yad2.co.il/realestate-feed/rent[/map] returns a
    {"data": {...}} envelope with the same listing shape.

Everything here is pure and unit-tested offline against fixtures.
"""
import json
import re

from bs4 import BeautifulSoup

# Yad2 region codes (region is REQUIRED by the gateway API since ~2026-03).
REGIONS = {
    1: "Center / Sharon",
    2: "South",
    3: "Tel Aviv",
    4: "Judea & Samaria",
    5: "North Coast (Haifa)",
    6: "Jerusalem",
    7: "North / Valleys",
}

# Minimal city-code -> region hint for the cities this project searches.
# 6400 = Rishon LeZion (Center). Resolve others via:
#   https://gw.yad2.co.il/address/v2/autocomplete?text=<hebrew-name>
REGION_BY_CITY = {
    "6400": 1,   # Rishon LeZion
    "5000": 3,   # Tel Aviv
    "3000": 6,   # Jerusalem
    "4000": 5,   # Haifa
}

# Listing buckets that are real listings (skip promos: trio, kingOfTheHar,
# leadingBroker, yad1).
LISTING_BUCKETS = ("private", "agency", "platinum", "booster")

def is_blocked(text, status=None):
    """True if the response is an anti-bot block/challenge instead of data.

    Discriminator: a real Yad2 search/item page ALWAYS embeds a
    <script id="__NEXT_DATA__"> blob (even a genuine 0-results search does).
    Its presence means "real page" (short-circuits, since pages inline JS that
    mentions captcha); its absence on any response means a challenge/interstitial
    (Radware "Radware Page" / perfdrive redirect) — not usable data."""
    if status is not None and status in (401, 403, 429):
        return True
    if not text:
        return True
    return "__NEXT_DATA__" not in text


def page_summary(text, status=None):
    """A one-line diagnostic for logs: status, size, data-blob presence, title."""
    if not text:
        return f"HTTP {status} empty-body"
    m = re.search(r"<title[^>]*>(.*?)</title>", text[:4000], re.I | re.S)
    title = m.group(1).strip()[:90] if m else ""
    return (f"HTTP {status} bytes={len(text)} "
            f"next_data={'__NEXT_DATA__' in text} title={title!r}")


def extract_next_data(html):
    """Return the parsed __NEXT_DATA__ dict, or None if not present."""
    if not html or "__NEXT_DATA__" not in html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        # Fallback: regex, in case the parser mangles a huge inline script.
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def _collect_from_data(data):
    """Pull raw listing objects out of a single React-Query/gateway `data`."""
    listings = []
    if not isinstance(data, dict):
        return listings
    for bucket in LISTING_BUCKETS:
        items = data.get(bucket)
        if isinstance(items, list):
            listings.extend(items)
    # Map endpoint returns markers instead of buckets.
    markers = data.get("markers")
    if isinstance(markers, list):
        listings.extend(markers)
    # Some paginated responses nest rows under pages[].
    for page in data.get("pages", []) or []:
        if isinstance(page, dict):
            listings.extend(page.get("data", []) or [])
    return listings


def extract_feed_listings(source):
    """Return raw listing objects from either a __NEXT_DATA__ dict or a
    gateway JSON envelope ({"data": {...}}). Accepts the already-parsed dict."""
    if not isinstance(source, dict):
        return []

    # Gateway JSON envelope: {"data": {"private": [...], ...}}.
    if "data" in source and "props" not in source:
        return _collect_from_data(source["data"])

    # __NEXT_DATA__ blob: walk the React-Query dehydrated cache.
    queries = (
        source.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries", [])
    )
    listings = []
    for q in queries:
        data = q.get("state", {}).get("data")
        listings.extend(_collect_from_data(data))
    return listings


def extract_item_detail(source):
    """Return the single rich item `data` object from an item page's
    __NEXT_DATA__ (or a gateway item envelope). The item now lives at
    dehydratedState.queries[0].state.data (the old hardcoded [1] is gone), so
    we locate it by shape (a dict carrying both `token` and `address`) rather
    than a fixed index."""
    if not isinstance(source, dict):
        return None
    if "data" in source and "props" not in source:
        data = source["data"]
        return data if isinstance(data, dict) and data.get("token") else None
    queries = (
        source.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries", [])
    )
    for q in queries:
        data = q.get("state", {}).get("data")
        if isinstance(data, dict) and data.get("token") and data.get("address"):
            return data
    return None


def _safe_date(value):
    """entranceDate may be a string, JSON null, or missing -> date or None."""
    if isinstance(value, str) and value:
        return value.split("T")[0]
    return None


def parse_item_detail(listing_data, link=None):
    """Map a rich item object (from the item gateway endpoint or the item
    page's dehydratedState) to this project's property_details schema.

    Field paths match the previous scrape_listing_page() output so downstream
    Google Sheets / Telegram code is unchanged.
    """
    if not isinstance(listing_data, dict):
        return None

    images_data = listing_data.get("metaData", {}).get("images", []) or []
    image_urls = []
    for img in images_data:
        if isinstance(img, str):
            image_urls.append(img)
        elif isinstance(img, dict):
            url = (
                img.get("url")
                or img.get("src")
                or img.get("href")
                or img.get("link")
                or img.get("original")
                or img.get("large")
            )
            if url:
                image_urls.append(url)

    tax = listing_data.get("propertyTax")
    address = listing_data.get("address", {}) or {}
    details = listing_data.get("additionalDetails", {}) or {}
    in_prop = listing_data.get("inProperty", {}) or {}
    meta = listing_data.get("metaData", {}) or {}

    return {
        "listing_id": listing_data.get("token"),
        "ad_number": listing_data.get("adNumber"),
        "city": address.get("city", {}).get("text"),
        "created_at": listing_data.get("dates", {}).get("createdAt"),
        "updated_at": listing_data.get("dates", {}).get("updatedAt"),
        "neighborhood": address.get("neighborhood", {}).get("text"),
        "street": address.get("street", {}).get("text"),
        "rent": listing_data.get("price"),
        "arnona_month": tax / 2 if isinstance(tax, (int, float)) and tax > 0 else None,
        "vaad": listing_data.get("houseCommittee"),
        "rooms": details.get("roomsCount"),
        "sqm": details.get("squareMeter"),
        "floor": address.get("house", {}).get("floor"),
        "elevator": in_prop.get("includeElevator"),
        "total_floors": details.get("buildingTopFloor"),
        "condition": details.get("propertyCondition", {}).get("text"),
        "entry": _safe_date(details.get("entranceDate")),
        "description": meta.get("description"),
        "search_text": meta.get("searchText"),
        "isLongTermContract": details.get("isLongTermContract"),
        "balcony": in_prop.get("includeBalcony"),
        "mamad": in_prop.get("includeSecurityRoom"),
        "parking": in_prop.get("includeParking"),
        "AC": in_prop.get("includeAirconditioner"),
        "Boiler": in_prop.get("includeBoiler"),
        "renovated": in_prop.get("isRenovated"),
        "furniture": listing_data.get("furnitureInfo", ""),
        "pets": in_prop.get("isPetsAllowed"),
        "latitude": address.get("coords", {}).get("lat"),
        "longitude": address.get("coords", {}).get("lon"),
        "tags": listing_data.get("tags", []),
        "property_type": details.get("property", {}).get("text"),
        "link": link,
        "image_count": len(images_data),
        "images": image_urls,
        "video_count": len(meta.get("videos", []) or []),
    }


def build_gateway_params(config_params):
    """Translate a search config's params into gateway-API params.

    The gateway requires `region` (a 400 is returned without it). We derive it
    from the city code when known; callers can also set region directly in the
    config. Legacy toggle flags (imageOnly/priceOnly/elevator/...) are passed
    through unchanged — unknown keys are ignored by the API.
    """
    params = dict(config_params)
    if "region" not in params:
        city = str(params.get("city", ""))
        region = REGION_BY_CITY.get(city)
        if region is not None:
            params["region"] = str(region)
    return params
