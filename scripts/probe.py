"""Quick end-to-end check that scraping works from THIS machine.

Runs one real search (region center-and-sharon) through the browser engine and
the shared parser, prints the listing count and a sample, and fetches one item
page. No Google Sheets / Telegram needed — use this to confirm your IP + browser
setup before running the full scripts/main.py.

Run from a RESIDENTIAL IP (datacenter/CI IPs are ASN-blocked by Radware):
    pip install -r requirements.txt
    patchright install chromium      # one-time browser download
    python scripts/probe.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # project root
sys.path.insert(0, os.path.dirname(__file__))  # scripts/ (sibling modules)

import yad2_fetch  # noqa: E402
import yad2_parse as yp  # noqa: E402
from config.search_configs import SCRAPER_CONFIG  # noqa: E402

SEARCH_URL = (
    SCRAPER_CONFIG["url"]
    + "?area=18&city=6400&minRooms=3&maxRooms=4.5&minPrice=5000&maxPrice=8000"
)


def main():
    print(f"Engine: {yad2_fetch.ENGINE}")
    with yad2_fetch.BrowserSession() as session:
        status, html = session.fetch(SEARCH_URL, timeout=60)
        print(f"Search: HTTP {status}  bytes={len(html)}  blocked={yp.is_blocked(html, status)}")
        nd = yp.extract_next_data(html)
        listings = yp.extract_feed_listings(nd) if nd else []
        print(f"Listings parsed: {len(listings)}")
        if not listings:
            print("No listings — if HTTP was 403/challenge you're on a blocked IP "
                  "(use a residential IP); otherwise the page structure changed.")
            return 1

        sample = yp.parse_item_detail(listings[0])
        print("Sample:", {k: sample.get(k) for k in
                          ("listing_id", "rent", "rooms", "sqm", "city", "neighborhood")})

        item_url = SCRAPER_CONFIG["base_item_url"] + listings[0]["token"]
        status, html = session.fetch(item_url, timeout=60)
        nd = yp.extract_next_data(html)
        detail = yp.extract_item_detail(nd) if nd else None
        if detail:
            d = yp.parse_item_detail(detail, link=item_url)
            print("Item detail OK:", {k: d.get(k) for k in
                                     ("listing_id", "elevator", "balcony", "mamad", "floor", "entry")})
        else:
            print(f"Item page: HTTP {status} blocked={yp.is_blocked(html, status)} — no detail")
    return 0


if __name__ == "__main__":
    sys.exit(main())
