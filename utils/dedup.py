"""Cross-source deduplication: match the SAME physical apartment listed on both
Yad2 and Madlan.

The within-Yad2 dedup in scraper.py keys on Yad2's `token` — useless across
sources, where the same flat has a different id on each site (and often slightly
different price/text). So we match on physical signals present in both parsers'
normalized output (see yad2_parse.parse_item_detail / madlan_parse):
geo-proximity + rooms + price. Falls back to normalized street+city+rooms when
coordinates are missing.

Pure and offline-testable. `group_duplicates` returns groups of listing dicts
that refer to the same property; `annotate_duplicates` tags each dict in place.
"""
import math
import re
import unicodedata

# Two listings are the same property if their coordinates are within this many
# metres AND rooms match AND price is close. 40 m ~= same building / adjacent
# entrance; listings' coords are often snapped to the building, not the flat.
GEO_METERS = 40.0
# Price tolerance: platforms disagree by a little (incl./excl. fees, stale edits).
PRICE_TOL_FRAC = 0.07
PRICE_TOL_ABS = 300  # shekels; whichever (frac|abs) is larger wins


def _haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _num(v):
    """Coerce prices/rooms/coords that may arrive as str/'1,234'/None/NaN to
    float (NaN and blanks -> None so they never count as a match signal)."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return None if math.isnan(v) else float(v)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)))
    except (ValueError, TypeError):
        return None


def _rooms_match(a, b):
    ra, rb = _num(a.get("rooms")), _num(b.get("rooms"))
    if ra is None or rb is None:
        return False
    return abs(ra - rb) < 0.01


def _price_close(a, b):
    pa, pb = _num(a.get("rent")), _num(b.get("rent"))
    if not pa or not pb:  # missing/zero price -> can't use it as a match signal
        return False
    tol = max(PRICE_TOL_ABS, PRICE_TOL_FRAC * max(pa, pb))
    return abs(pa - pb) <= tol


def _norm_text(s):
    """Lowercase, strip Hebrew niqqud/punctuation/whitespace for street compare."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w֐-׿]+", " ", s)  # keep word chars + Hebrew block
    return s.strip().lower()


def _coords(x):
    lat, lon = _num(x.get("latitude")), _num(x.get("longitude"))
    if lat is None or lon is None or (lat == 0 and lon == 0):
        return None
    return lat, lon


def is_same_property(a, b):
    """True if a and b are very likely the same physical apartment.

    Requires rooms + price agreement in both branches; geo is the strong signal,
    street+city the fallback when either side lacks coordinates."""
    # Only ever match ACROSS sources. Two listings from the SAME source already
    # have distinct native IDs, so treating physically-close same-source listings
    # (common when one building has several units on the market) as duplicates
    # would wrongly collapse real, separate listings.
    sa, sb = a.get("source"), b.get("source")
    if sa is not None and sb is not None and sa == sb:
        return False
    if not _rooms_match(a, b) or not _price_close(a, b):
        return False
    ca, cb = _coords(a), _coords(b)
    if ca and cb:
        return _haversine_m(ca[0], ca[1], cb[0], cb[1]) <= GEO_METERS
    # Fallback: same city + same normalized street (house number if present).
    if _norm_text(a.get("city")) != _norm_text(b.get("city")):
        return False
    sa, sb = _norm_text(a.get("street")), _norm_text(b.get("street"))
    return bool(sa) and sa == sb


def group_duplicates(listings):
    """Group listings that refer to the same property. Returns a list of groups
    (each a list of the original dicts); singletons are groups of length 1.

    O(n^2) pairwise — fine for the few-hundred listings this project handles.
    ponytail: if the combined feed ever grows to thousands, bucket by a coarse
    geohash / (city,rooms) first and only compare within a bucket."""
    parent = list(range(len(listings)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(listings)):
        for j in range(i + 1, len(listings)):
            if find(i) != find(j) and is_same_property(listings[i], listings[j]):
                parent[find(i)] = find(j)

    groups = {}
    for idx in range(len(listings)):
        groups.setdefault(find(idx), []).append(listings[idx])
    return list(groups.values())


def annotate_duplicates(listings):
    """Tag each listing in place and return `listings`. Adds:
      dup_group_id  – stable id shared by all members of a duplicate group
      dup_sources   – sorted unique `source` values in the group (e.g. yad2,madlan)
      is_primary    – True for one representative per group (prefers the richest
                      record: most non-empty fields, tie-broken by source order)
    A group with one member is still tagged (dup_sources = [its source])."""
    source_rank = {"yad2": 0, "madlan": 1}
    for gid, group in enumerate(group_duplicates(listings)):
        sources = sorted({(g.get("source") or "unknown") for g in group})
        primary = max(
            group,
            key=lambda g: (
                sum(1 for v in g.values() if v not in (None, "", [], {})),
                -source_rank.get(g.get("source"), 99),
            ),
        )
        for g in group:
            g["dup_group_id"] = gid
            g["dup_sources"] = sources
            g["is_primary"] = g is primary
    return listings


def combine_and_dedupe(dataframes):
    """Concatenate per-source DataFrames (e.g. Yad2 + Madlan), tag cross-source
    duplicates, and return one annotated DataFrame. Rows missing `source` are
    labelled 'unknown'. Adds the dup_group_id / dup_sources / is_primary columns
    from annotate_duplicates. Keep only cross-source primaries with
    `df[df.is_primary]` if you want a single row per physical property."""
    import pandas as pd
    frames = [d for d in dataframes if d is not None and not d.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    if "source" not in combined.columns:
        combined["source"] = "unknown"
    combined["source"] = combined["source"].fillna("unknown")
    records = combined.to_dict("records")
    annotate_duplicates(records)
    return pd.DataFrame(records)


if __name__ == "__main__":
    # One runnable check: same flat on both sites (coords 12 m apart, same rooms,
    # 3% price gap) collapses to a 2-source group; a different flat stays separate.
    y = {"source": "yad2", "listing_id": "y1", "latitude": 32.1650, "longitude": 34.8420,
         "rooms": 3.5, "rent": 8000, "city": "הרצליה", "street": "סוקולוב"}
    m = {"source": "madlan", "listing_id": "m1", "latitude": 32.16509, "longitude": 34.84210,
         "rooms": 3.5, "rent": 8200, "city": "הרצליה", "street": "סוקולוב"}
    other = {"source": "madlan", "listing_id": "m2", "latitude": 32.1800, "longitude": 34.8600,
             "rooms": 4, "rent": 6000, "city": "הרצליה", "street": "בן גוריון"}
    groups = group_duplicates([y, m, other])
    assert len(groups) == 2, groups
    assert any(len(g) == 2 for g in groups), "y1 and m1 should merge"
    annotate_duplicates([y, m, other])
    assert y["dup_group_id"] == m["dup_group_id"] and y["dup_sources"] == ["madlan", "yad2"]
    assert other["dup_sources"] == ["madlan"]
    print("dedup self-test OK")
