"""Offline unit tests for the Madlan scraper: parsing + cross-source dedup.

No network. Fixtures (tests/fixtures/madlan_*_poi.json) are REAL poi objects
captured by scripts/madlan_probe.py from the Herzliya rent search + one item
page, trimmed to the listing objects. See docs/MADLAN_SCRAPING.md.
"""
import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import madlan_parse as mp  # noqa: E402
from utils import dedup  # noqa: E402

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


def test_expected_city_doc_id_from_url():
    import madlan_scraper as ms
    url = ("https://www.madlan.co.il/for-rent/%D7%94%D7%A8%D7%A6%D7%9C%D7%99%D7%94-"
           "%D7%99%D7%A9%D7%A8%D7%90%D7%9C?filters=_5000-8500_3-4.5")
    assert ms._expected_city_doc_id(url) == "הרצליה-ישראל"
    assert ms._expected_city_doc_id("https://www.madlan.co.il/for-sale/רעננה-ישראל") == "רעננה-ישראל"
    assert ms._expected_city_doc_id(url, override="custom") == "custom"
    assert ms._expected_city_doc_id("https://www.madlan.co.il/listings/abc") is None


def test_keep_in_city_drops_nearby():
    # Real Herzliya search feed pads with nearby-city listings (totalNearby>0);
    # a Ramat HaSharon flat must be dropped so it isn't scraped/notified.
    import madlan_scraper as ms
    herz = _load("madlan_search_poi.json")  # 3 pois, cityDocId הרצליה-ישראל
    nearby = {"id": "rx1", "addressDetails": {"cityDocId": "רמת-השרון-ישראל",
                                              "city": "רמת השרון"}}
    kept = ms._keep_in_city(herz + [nearby], "הרצליה-ישראל")
    assert len(kept) == 3
    assert all(p["addressDetails"]["cityDocId"] == "הרצליה-ישראל" for p in kept)
    # No city -> no filtering (backward compatible).
    assert ms._keep_in_city(herz + [nearby], None) == herz + [nearby]


def test_parse_item_detail():
    row = mp.parse_listing(_load("madlan_item_poi.json"))
    assert row["listing_id"] == "XcM1UBEhHDU"
    assert row["source"] == "madlan"
    assert row["rent"] == 7500 and row["rooms"] == 4.5 and row["sqm"] == 110
    assert row["city"] == "הרצליה" and row["street"] == "אחד העם 42"
    assert row["floor"] == 2 and row["total_floors"] == 3
    assert row["elevator"] is True and row["shelter"] is True and row["balcony"] is True
    assert abs(row["latitude"] - 32.1654) < 0.01
    assert row["image_count"] == 9
    assert row["images"][0].startswith("https://images2.madlan.co.il")
    assert row["link"] == "https://www.madlan.co.il/listings/XcM1UBEhHDU"


def test_item_detail_amenities_reported():
    # The elevator bug: amenities must be read correctly from the item detail.
    row = mp.parse_listing(_load("madlan_item_poi.json"))
    assert row["elevator"] is True   # <- the field that was being missed
    assert row["AC"] is True
    assert row["shelter"] is True
    assert row["mamad"] is False
    assert row["balcony"] is True


def test_feed_rows_have_no_amenities():
    # Root cause: the search FEED carries no `amenities` object, so amenity
    # fields are None on feed-only rows — which the notifier renders as "No".
    # This is WHY the scraper must enrich from the item page (fetch_details).
    for poi in _load("madlan_search_poi.json"):
        assert "amenities" not in poi
        row = mp.parse_listing(poi)
        assert row["elevator"] is None
        assert row["mamad"] is None and row["shelter"] is None and row["AC"] is None


def test_scraper_fetches_details_by_default():
    # Guards the fix: detail-fetch (which carries amenities) must stay on by
    # default, else Madlan rows lose elevator/mamad/shelter/AC accuracy.
    import madlan_scraper
    assert madlan_scraper.MadlanScraper().fetch_details is True


@pytest.mark.skipif(
    not os.path.exists(os.path.join(FX, "madlan_item_hC1zbsjUN2E.json")),
    reason="capture with: python scripts/madlan_probe.py hC1zbsjUN2E "
           "(then copy data/madlan_fixtures/item_poi.json to "
           "tests/fixtures/madlan_item_hC1zbsjUN2E.json)",
)
def test_reported_listing_hC1zbsjUN2E_has_elevator():
    # The exact listing the user reported as wrongly flagged 'no elevator'.
    row = mp.parse_listing(_load("madlan_item_hC1zbsjUN2E.json"))
    assert row["elevator"] is True


def test_parse_feed():
    rows = [mp.parse_listing(p) for p in _load("madlan_search_poi.json")]
    assert len(rows) == 3
    assert all(r["listing_id"] and r["source"] == "madlan" for r in rows)
    assert all(isinstance(r["rent"], (int, float)) for r in rows)


def test_extract_ssr_context_handles_undefined():
    # The real SSR blob is a JS object literal with bare `undefined` tokens.
    poi = _load("madlan_item_poi.json")
    html = ('<html><body><script>window.__SSR_HYDRATED_CONTEXT__='
            '{"reduxInitialState":{"domainData":{"bulletinsByIds":{"data":'
            '{"poiByIds":[' + json.dumps(poi) + ']},"loading":false,'
            '"networkStatus":7,"meta":{"missing":undefined,"ok":"undefined"}}}}}}'
            '</script></body></html>')
    ctx = mp.extract_ssr_context(html)
    assert ctx is not None
    detail = mp.extract_item_detail(ctx)
    assert detail["id"] == "XcM1UBEhHDU"
    # A quoted "undefined" string must survive; only the bare token becomes null.
    meta = ctx["reduxInitialState"]["domainData"]["bulletinsByIds"]["meta"]
    assert meta["missing"] is None and meta["ok"] == "undefined"


def test_is_blocked():
    assert mp.is_blocked("", 200) is True
    assert mp.is_blocked("<html>px-captcha please press & hold</html>", 403) is True
    assert mp.is_blocked("<html><script>window.__SSR_HYDRATED_CONTEXT__={}</script></html>", 200) is False
    # PX sensor script alone (present on good pages too) is NOT a block:
    assert mp.is_blocked("<html>window._pxAppId='o4wPDYYd' "
                         "window.__SSR_HYDRATED_CONTEXT__={}</html>", 200) is False


def _yad2_row_same_flat_as_item():
    """A Yad2-shaped row for the SAME physical flat as the Madlan item fixture
    (coords ~a few m apart, same 4.5 rooms, 2% price gap)."""
    return {
        "source": "yad2", "listing_id": "yad2-987",
        "latitude": 32.16547, "longitude": 34.84577,
        "rooms": 4.5, "rent": 7650, "city": "הרצליה", "street": "אחד העם 42",
    }


def test_search_pois_from_nested_graphql():
    import madlan_fetch  # noqa: E402
    poi = _load("madlan_search_poi.json")
    # Mimic a 'load more' GraphQL envelope: {data: {searchPoiV2: {poi: [...]}}}.
    resp = {"data": {"searchPoiV2": {"total": 42, "poi": poi}}}
    found = madlan_fetch._search_pois_from(resp)
    assert [p["id"] for p in found] == [p["id"] for p in poi]
    assert madlan_fetch._search_pois_from({"data": None}) == []


def test_same_source_listings_never_merged():
    # Two DISTINCT Madlan listings in the same building (identical coords/rooms/
    # price) must NOT be merged — same source already has unique IDs. Regression
    # for the over-merge that collapsed distinct Herzliya-center listings.
    a = {"source": "madlan", "listing_id": "m1", "latitude": 32.16, "longitude": 34.84,
         "rooms": 3, "rent": 8000, "city": "הרצליה", "street": "סוקולוב 1"}
    b = {"source": "madlan", "listing_id": "m2", "latitude": 32.16, "longitude": 34.84,
         "rooms": 3, "rent": 8000, "city": "הרצליה", "street": "סוקולוב 1"}
    assert dedup.is_same_property(a, b) is False
    assert len(dedup.group_duplicates([a, b])) == 2


def test_cross_source_dedup_matches_same_flat():
    madlan_row = mp.parse_listing(_load("madlan_item_poi.json"))
    yad2_row = _yad2_row_same_flat_as_item()
    assert dedup.is_same_property(madlan_row, yad2_row) is True
    groups = dedup.group_duplicates([madlan_row, yad2_row])
    assert len(groups) == 1 and len(groups[0]) == 2


def test_cross_source_dedup_keeps_distinct_flats():
    rows = [mp.parse_listing(p) for p in _load("madlan_search_poi.json")]
    # Three different listings at different addresses must NOT collapse.
    groups = dedup.group_duplicates(rows)
    assert len(groups) == 3


def test_combine_and_dedupe_dataframes():
    madlan_df = pd.DataFrame([mp.parse_listing(p) for p in _load("madlan_search_poi.json")])
    yad2_df = pd.DataFrame([_yad2_row_same_flat_as_item()])
    combined = dedup.combine_and_dedupe([yad2_df, madlan_df])
    assert len(combined) == 4  # 3 madlan + 1 yad2 rows, annotated (not collapsed)
    # The yad2 row and the matching madlan item share a dup group spanning sources.
    xcm = combined[combined.listing_id == "XcM1UBEhHDU"].iloc[0]
    assert set(xcm["dup_sources"]) == {"yad2", "madlan"}
    assert (combined["dup_sources"].apply(lambda s: set(s) == {"yad2", "madlan"})).sum() == 2
