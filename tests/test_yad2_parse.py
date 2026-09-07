"""Offline unit tests for scripts/yad2_parse.py.

No network. Fixtures reconstruct the documented 2026 Yad2 shapes:
  * gateway JSON envelope {"data": {private/agency/platinum/booster: [...]}}
  * __NEXT_DATA__ blob with props.pageProps.dehydratedState.queries[].state.data
  * a Radware/ShieldSquare block page

When you capture a REAL response on your Mac (the probe scripts dump one to
data/sample_*.json), replace/extend these fixtures with it to lock parsing to
the live shape.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import yad2_parse as yp  # noqa: E402


def _item(token, price, rooms):
    return {
        "token": token,
        "adNumber": 1000 + int(token[-1]) if token[-1].isdigit() else None,
        "price": price,
        "propertyTax": 400,
        "address": {
            "city": {"text": "ראשון לציון"},
            "neighborhood": {"text": "נווה ים"},
            "street": {"text": "הרצל"},
            "house": {"number": 10, "floor": 3},
            "coords": {"lat": 31.97, "lon": 34.79},
        },
        "additionalDetails": {
            "roomsCount": rooms,
            "squareMeter": 80,
            "property": {"text": "דירה"},
            "entranceDate": "2026-10-01T00:00:00Z",
        },
        "inProperty": {"includeElevator": True, "includeBalcony": True},
        "metaData": {"images": ["https://img/1.jpg", {"url": "https://img/2.jpg"}]},
    }


GATEWAY_JSON = {
    "data": {
        "private": [_item("abc1", 5500, 3)],
        "agency": [_item("abc2", 6200, 4)],
        "platinum": [],
        "trio": [{"token": "PROMO", "price": 0}],  # promo bucket -> ignored
    }
}

NEXT_DATA = {
    "props": {
        "pageProps": {
            "dehydratedState": {
                "queries": [
                    {"state": {"data": {"markers": [_item("m1", 4800, 3)]}}},
                    {"state": {"data": {"private": [_item("m2", 7000, 5)]}}},
                ]
            }
        }
    }
}

NEXT_DATA_HTML = (
    "<html><head></head><body>"
    '<script id="__NEXT_DATA__" type="application/json">'
    + json.dumps(NEXT_DATA)
    + "</script></body></html>"
)

BLOCK_HTML = (
    "<!DOCTYPE html><html><head><title>403 Forbidden</title></head>"
    "<body><h2>403 Forbidden</h2><h2>Transaction ID:</h2> deadbeef</body></html>"
)


def test_is_blocked_detects_waf_page():
    assert yp.is_blocked(BLOCK_HTML) is True
    assert yp.is_blocked("anything", status=403) is True
    assert yp.is_blocked("", status=200) is True


def test_is_blocked_false_on_real_html():
    assert yp.is_blocked(NEXT_DATA_HTML, status=200) is False


def test_extract_from_gateway_json_skips_promos():
    listings = yp.extract_feed_listings(GATEWAY_JSON)
    tokens = {x["token"] for x in listings}
    assert tokens == {"abc1", "abc2"}  # PROMO in `trio` excluded


def test_extract_next_data_and_feed_from_html():
    nd = yp.extract_next_data(NEXT_DATA_HTML)
    assert nd is not None
    listings = yp.extract_feed_listings(nd)
    tokens = {x["token"] for x in listings}
    assert tokens == {"m1", "m2"}  # markers + private buckets both collected


def test_extract_next_data_returns_none_when_absent():
    assert yp.extract_next_data(BLOCK_HTML) is None
    assert yp.extract_next_data("") is None


def test_parse_item_detail_maps_core_fields():
    d = yp.parse_item_detail(_item("abc1", 5500, 3), link="https://x/item/abc1")
    assert d["listing_id"] == "abc1"
    assert d["rent"] == 5500
    assert d["rooms"] == 3
    assert d["sqm"] == 80
    assert d["city"] == "ראשון לציון"
    assert d["floor"] == 3
    assert d["elevator"] is True
    assert d["arnona_month"] == 200  # propertyTax 400 / 2
    assert d["entry"] == "2026-10-01"
    assert d["image_count"] == 2
    assert d["images"] == ["https://img/1.jpg", "https://img/2.jpg"]
    assert d["link"] == "https://x/item/abc1"


def test_parse_item_detail_handles_null_entrance_date():
    item = _item("abc1", 5500, 3)
    item["additionalDetails"]["entranceDate"] = None  # JSON null, not missing
    d = yp.parse_item_detail(item)
    assert d["entry"] is None  # must not raise AttributeError


def test_build_gateway_params_injects_region_from_city():
    out = yp.build_gateway_params({"city": "6400", "minRooms": "3"})
    assert out["region"] == "1"  # Rishon LeZion -> Center
    assert out["city"] == "6400"
    assert out["minRooms"] == "3"


def test_build_gateway_params_keeps_explicit_region():
    out = yp.build_gateway_params({"city": "6400", "region": "9"})
    assert out["region"] == "9"
