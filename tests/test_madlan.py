"""Offline unit tests for the Madlan scraper: parsing + cross-source dedup.

No network. Fixtures (tests/fixtures/madlan_*_poi.json) are REAL poi objects
captured by scripts/madlan_probe.py from the Herzliya rent search + one item
page, trimmed to the listing objects. See docs/MADLAN_SCRAPING.md.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import madlan_parse as mp  # noqa: E402
from utils import dedup  # noqa: E402

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return json.load(f)


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
