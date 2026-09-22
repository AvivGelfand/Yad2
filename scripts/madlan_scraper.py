"""Madlan rental scraper — the Madlan counterpart of scripts/scraper.py.

Fetches each configured Madlan search URL through a headful browser (past
PerimeterX), parses the embedded results into the shared listing schema
(source="madlan"), optionally enriches each from its item page, and returns a
pandas DataFrame ready to be combined + deduped with the Yad2 output.

Run standalone:  /path/to/python scripts/madlan_scraper.py
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # sibling madlan_fetch / madlan_parse

import pandas as pd

import madlan_fetch
import madlan_parse as mp
from config.madlan_searches import (
    MADLAN_SEARCHES, MADLAN_FETCH_DETAILS, MADLAN_MAX_RESULTS,
)


class MadlanBlocked(Exception):
    """Raised when PerimeterX/Cloudflare blocks the request. Almost always means
    a datacenter/CI IP or a cold profile — run headful from a residential IP."""


class MadlanScraper:
    def __init__(self, searches=None, fetch_details=None, max_results=None):
        self.searches = searches or MADLAN_SEARCHES
        self.fetch_details = (MADLAN_FETCH_DETAILS if fetch_details is None
                              else fetch_details)
        self.max_results = MADLAN_MAX_RESULTS if max_results is None else max_results
        self._session = None

    def _fetch(self, url):
        return self._session.fetch(url)

    def fetch_feed(self, url):
        """Fetch one search URL -> list of raw poi dicts. Merges the ~15 results
        embedded in the SSR blob with any extra pages the browser loads on scroll
        (see MadlanSession.fetch_search), deduped by id."""
        status, html, extra = self._session.fetch_search(url, want=self.max_results)
        if mp.is_blocked(html, status):
            raise MadlanBlocked(
                f"Madlan blocked on search. {mp.page_summary(html, status)}. "
                f"Run headful (MADLAN_HEADFUL=1) from a residential IP."
            )
        ctx = mp.extract_ssr_context(html)
        feed = mp.extract_feed_listings(ctx) if ctx else []
        # searchPoiV2.total tells us how many matched overall.
        total = None
        data = (ctx or {}).get("reduxInitialState", {}).get("domainData", {}) \
            .get("searchList", {}).get("data")
        if isinstance(data, dict):
            total = data.get("searchPoiV2", {}).get("total")
        # Merge SSR feed + scroll-loaded extras (dedup by id; SSR wins on conflict).
        by_id = {p["id"]: p for p in feed if p.get("id")}
        for p in extra:
            by_id.setdefault(p["id"], p)
        merged = list(by_id.values())
        note = ""
        if total and len(merged) < total:
            note = (f" (got {len(merged)}/{total}; more exist — raise MADLAN_MAX_RESULTS "
                    f"or scrolling didn't reach them)")
        print(f"  parsed {len(merged)} listings" + (f" of {total} matched" if total else "") + note)
        return merged

    def enrich(self, listing_id):
        """Fetch an item page and return the fully-parsed detail row, or None."""
        url = f"https://www.madlan.co.il/listings/{listing_id}"
        status, html = self._fetch(url)
        if mp.is_blocked(html, status):
            raise MadlanBlocked(f"Madlan blocked on item {listing_id}. "
                                f"{mp.page_summary(html, status)}")
        ctx = mp.extract_ssr_context(html)
        poi = mp.extract_item_detail(ctx) if ctx else None
        return mp.parse_listing(poi, link=url) if poi else None

    def run(self):
        """Scrape all searches -> deduped (by listing_id) DataFrame."""
        rows, seen = [], set()
        with madlan_fetch.MadlanSession() as session:
            self._session = session
            print(f"🌐 Madlan engine: {madlan_fetch.ENGINE} "
                  f"(headful={session._headful})")
            for i, cfg in enumerate(self.searches, 1):
                print(f"\n=== Madlan search {i}/{len(self.searches)}: {cfg['name']} ===")
                try:
                    feed = self.fetch_feed(cfg["url"])
                except MadlanBlocked as e:
                    print(f"❌ {e}")
                    raise
                for poi in feed:
                    lid = poi.get("id")
                    if not lid or lid in seen:
                        continue
                    seen.add(lid)
                    if self.fetch_details:
                        try:
                            row = self.enrich(lid)
                        except MadlanBlocked:
                            raise
                        except Exception as ex:
                            print(f"  ⚠️ enrich {lid} failed: {ex}; using feed row")
                            row = mp.parse_listing(poi)
                        time.sleep(0.5)
                    else:
                        row = mp.parse_listing(poi)
                    if row:
                        row["search_config"] = cfg["name"]
                        rows.append(row)
                if i < len(self.searches):
                    time.sleep(2)
        print(f"\n📊 Madlan: {len(rows)} unique listings")
        return pd.DataFrame(rows)


if __name__ == "__main__":
    df = MadlanScraper().run()
    if df.empty:
        print("No Madlan listings found")
        sys.exit(1)
    cols = ["listing_id", "city", "neighborhood", "street", "rent", "rooms",
            "sqm", "latitude", "longitude"]
    print("\n" + df[cols].to_string(index=False))
    out = os.path.join(os.path.dirname(__file__), "..", "data", "madlan_listings.csv")
    df.to_csv(out, index=False)
    print(f"\nSaved {len(df)} rows -> {out}")
