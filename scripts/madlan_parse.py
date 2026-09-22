"""Engine-agnostic parsing for Madlan rental data.

Like yad2_parse, this module knows nothing about how the HTML was fetched — it
turns a rendered Madlan page into listing dicts on the SAME normalized schema
yad2_parse.parse_item_detail emits, plus a `source` field, so downstream
Sheets/Telegram/dedup code treats both sources uniformly.

Where the data lives (discovered from real fixtures, see docs/MADLAN_SCRAPING.md):
Madlan is a @loadable React app that embeds its Redux/Apollo hydration state in
    <script>window.__SSR_HYDRATED_CONTEXT__={...}</script>
(NOT __NEXT_DATA__). Inside `reduxInitialState.domainData` (an Apollo-style cache
keyed by query name, each {data, loading, networkStatus, ...}):
  * search page -> searchList.data.searchPoiV2.poi         (list of listings)
  * item  page  -> bulletinsByIds.data.poiByIds            (single-element list)
The blob is a JS object literal, not strict JSON — it contains bare `undefined`
tokens that must be neutralised before json.loads.
"""
import json
import re
from datetime import datetime

# Image paths in the feed are host-relative ("/bulletins/<uuid>.jpeg"); the raw
# path 302-redirects, but this transform prefix (copied from the page's ld+json)
# serves the image directly (HTTP 200, webp). The image CDN is NOT behind the PX
# WAF, so photos download with plain requests (like Yad2's img CDN).
IMG_CDN = "https://images2.madlan.co.il/t:nonce:v=5;convert:type=webp"

_SSR_KEY = "window.__SSR_HYDRATED_CONTEXT__="
# Replace bare `undefined` value tokens (after : , or [ and before , } or ])
# with null. Quoted "undefined" strings are untouched (preceded by ").
_UNDEF = re.compile(r'(?<=[:,\[])undefined(?=[,}\]])')

# A real anti-bot block = 403/429 or the PX interactive captcha. The PX sensor
# script (_pxAppId / client.px-cloud.net) runs on EVERY page including good ones,
# so its presence is NOT a block signal — the presence of the SSR blob is proof
# of a real page and short-circuits to "not blocked".
_BLOCK_SIGS = ("px-captcha", "captcha-delivery", "לחשוב שאתה רובוט",
               "press & hold", "לחצו והחזיקו", "attention required")


def is_blocked(text, status=None):
    """True only if the response is a genuine PerimeterX/Cloudflare block page."""
    if text and _SSR_KEY in text:
        return False
    if status is not None and status in (401, 403, 429):
        return True
    if not text:
        return True
    lowered = text[:12000].lower()
    return any(sig in lowered or sig in text[:12000] for sig in _BLOCK_SIGS)


def page_summary(text, status=None):
    """One-line diagnostic for logs."""
    if not text:
        return f"HTTP {status} empty-body"
    m = re.search(r"<title[^>]*>(.*?)</title>", text[:4000], re.I | re.S)
    title = m.group(1).strip()[:80] if m else ""
    return (f"HTTP {status} bytes={len(text)} "
            f"ssr={_SSR_KEY in text} title={title!r}")


def extract_ssr_context(html):
    """Return the parsed window.__SSR_HYDRATED_CONTEXT__ dict, or None."""
    if not html or _SSR_KEY not in html:
        return None
    i = html.find(_SSR_KEY) + len(_SSR_KEY)
    tail = _UNDEF.sub("null", html[i:])
    try:
        obj, _ = json.JSONDecoder().raw_decode(tail, 0)
        return obj
    except json.JSONDecodeError:
        return None


def _domain_query(ctx, key):
    """reduxInitialState.domainData[key].data, or None if unpopulated."""
    if not isinstance(ctx, dict):
        return None
    node = ctx.get("reduxInitialState", {}).get("domainData", {}).get(key)
    if isinstance(node, dict):
        return node.get("data")
    return None


def extract_feed_listings(ctx):
    """Return the raw `poi` list from a search page's SSR context."""
    data = _domain_query(ctx, "searchList")
    poi = (data or {}).get("searchPoiV2", {}).get("poi") if isinstance(data, dict) else None
    return poi if isinstance(poi, list) else []


def extract_item_detail(ctx):
    """Return the single rich poi object from an item page's SSR context."""
    for key in ("bulletinsByIds", "commercialBulletinsByIds"):
        data = _domain_query(ctx, key)
        poi = (data or {}).get("poiByIds") if isinstance(data, dict) else None
        if isinstance(poi, list) and poi:
            return poi[0]
    return None


def _num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return int(v) if v.isdigit() else float(v)
        except ValueError:
            return None
    return None


def _entry_date(value):
    """availableDate is a JS Date string ('Wed Sep 30 21:00:00 GMT 2026') or an
    ISO string; return YYYY-MM-DD, else the raw value, else None."""
    if not isinstance(value, str) or not value:
        return None
    if "T" in value and "-" in value:  # ISO
        return value.split("T")[0]
    try:
        return datetime.strptime(value, "%a %b %d %H:%M:%S GMT %Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def _image_urls(images):
    out = []
    for img in images or []:
        path = img.get("imageUrl") if isinstance(img, dict) else (img if isinstance(img, str) else None)
        if path:
            out.append(IMG_CDN + path if path.startswith("/") else path)
    return out


def parse_listing(poi, link=None):
    """Map a Madlan `poi` (from search feed OR item detail) to the shared schema.

    Amenity/detail fields (description, amenities, floors, vaad, taxes) exist only
    on the item-detail poi; feed pois carry the core fields (price, rooms, area,
    coords, address, images) — enough for dedup and a listing row. Missing keys
    resolve to None so both poi shapes parse without error.
    """
    if not isinstance(poi, dict):
        return None

    addr = poi.get("addressDetails") or {}
    am = poi.get("amenities") or {}
    extra_areas = am.get("additionalAreas") or {}
    listing_id = poi.get("id")
    street = addr.get("streetName")
    if street and addr.get("streetNumber"):
        street = f"{street} {addr['streetNumber']}"

    # balcony: the boolean is often null even when a balcony exists; the
    # additionalAreas.balconyAreas list is the reliable signal.
    balcony = am.get("balcony") or am.get("julietBalcony") \
        or bool(extra_areas.get("balconyAreas"))

    return {
        "listing_id": listing_id,
        "ad_number": poi.get("originalId"),
        "city": addr.get("city"),
        "created_at": poi.get("firstTimeSeen"),
        "updated_at": poi.get("lastUpdated"),
        "neighborhood": addr.get("neighbourhood"),
        "street": street,
        "rent": _num(poi.get("price")),
        "arnona_month": _num(poi.get("monthlyTaxes")),
        "vaad": _num(poi.get("commonCharges")),
        "rooms": _num(poi.get("beds")),
        "sqm": _num(poi.get("area")),
        "floor": _num(poi.get("floor")),
        "elevator": am.get("elevator"),
        "total_floors": _num(poi.get("floors")),
        "condition": poi.get("generalCondition"),
        "entry": _entry_date(poi.get("availableDate")),
        "description": poi.get("description"),
        "search_text": poi.get("description"),
        "isLongTermContract": None,
        "balcony": balcony,
        "mamad": am.get("secureRoom") or am.get("mamak"),
        "shelter": am.get("miklat"),
        "parking": bool(poi.get("parking")) or am.get("garage"),
        "AC": am.get("airConditioner"),
        "Boiler": am.get("sunBoiler"),
        "renovated": poi.get("generalCondition") in ("renovated", "new"),
        "furniture": am.get("isFurnished") if am.get("isFurnished") is not None else am.get("furnished"),
        "pets": am.get("unitPetsAllowed"),
        "latitude": (poi.get("locationPoint") or {}).get("lat"),
        "longitude": (poi.get("locationPoint") or {}).get("lng"),
        "tags": poi.get("tags"),
        "property_type": poi.get("buildingClass"),
        "link": link or (f"https://www.madlan.co.il/listings/{listing_id}" if listing_id else None),
        "image_count": len(poi.get("images") or []),
        "images": _image_urls(poi.get("images")),
        "video_count": len(poi.get("virtualTours") or []),
        "source": "madlan",
    }


if __name__ == "__main__":
    # Self-test against the real fixtures captured by scripts/madlan_probe.py.
    import os
    fx = os.path.join(os.path.dirname(__file__), "..", "data", "madlan_fixtures")
    item_html = open(os.path.join(fx, "item.html"), encoding="utf-8").read()
    search_html = open(os.path.join(fx, "search.html"), encoding="utf-8").read()

    assert not is_blocked(item_html, 200) and not is_blocked(search_html, 200)

    ctx = extract_ssr_context(item_html)
    detail = parse_listing(extract_item_detail(ctx))
    print("ITEM parsed:", json.dumps(
        {k: detail[k] for k in ("listing_id", "city", "street", "neighborhood",
         "rent", "rooms", "sqm", "floor", "total_floors", "elevator", "mamad",
         "shelter", "balcony", "AC", "latitude", "longitude", "image_count",
         "source")}, ensure_ascii=False, indent=1))
    assert detail["listing_id"] == "XcM1UBEhHDU"
    assert detail["rent"] == 7500 and detail["rooms"] == 4.5 and detail["sqm"] == 110
    assert detail["city"] == "הרצליה" and detail["elevator"] is True
    assert detail["shelter"] is True and detail["source"] == "madlan"
    assert detail["images"] and detail["images"][0].startswith("https://images2.madlan.co.il")

    feed = extract_feed_listings(extract_ssr_context(search_html))
    parsed = [parse_listing(p) for p in feed]
    print(f"\nSEARCH parsed {len(parsed)} listings; sample rents/rooms:",
          [(p["rent"], p["rooms"]) for p in parsed[:5]])
    assert len(parsed) >= 5 and all(p["listing_id"] and p["source"] == "madlan" for p in parsed)
    print("\nmadlan_parse self-test OK")
