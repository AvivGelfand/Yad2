"""A single blocked item page must not abort the whole run.

Item-page Radware challenges are probabilistic and usually recover on retry, so
scrape_listings_pages skips a blocked item and keeps the harvest, aborting early
only after BLOCK_STREAK_LIMIT consecutive blocks — and even then it returns what
it already scraped rather than discarding it. See docs/ANTI_BOT_HANDLING.md §4-5.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import scraper as sc  # noqa: E402


def _bare_scraper(monkeypatch):
    # Skip the heavy __init__ (notifier, tracker, settings); scrape_listings_pages
    # only needs these attrs plus two module-level deps we stub out.
    s = sc.Yad2MultiSearchScraper.__new__(sc.Yad2MultiSearchScraper)
    s.scraped_listings = {}
    s.enable_notifications = False  # makes _notify_error a no-op
    monkeypatch.setattr(sc, "save_property_photos", lambda *_a, **_k: 0)
    monkeypatch.setattr(sc.time, "sleep", lambda *_a, **_k: None)
    return s


def _token_of(url):
    return url[len(sc.SCRAPER_CONFIG["base_item_url"]):]


def _listings(*tokens):
    return [{"token": t, "search_config": "s"} for t in tokens]


def test_single_item_block_is_skipped_and_run_keeps_going(monkeypatch):
    s = _bare_scraper(monkeypatch)

    def fake_scrape(url):
        tok = _token_of(url)
        if tok == "b":
            raise sc.Yad2Blocked("blocked b")
        return {"listing_id": tok, "images": []}

    monkeypatch.setattr(s, "scrape_listing_page", fake_scrape)

    df = s.scrape_listings_pages(_listings("a", "b", "c"))

    assert not df.empty
    assert set(df["listing_id"]) == {"a", "c"}  # blocked 'b' skipped, rest kept


def test_consecutive_block_streak_stops_early_but_returns_harvest(monkeypatch):
    s = _bare_scraper(monkeypatch)
    scraped = []

    def fake_scrape(url):
        tok = _token_of(url)
        scraped.append(tok)
        if tok == "good":
            return {"listing_id": tok, "images": []}
        raise sc.Yad2Blocked("blocked " + tok)

    monkeypatch.setattr(s, "scrape_listing_page", fake_scrape)

    limit = sc.Yad2MultiSearchScraper.BLOCK_STREAK_LIMIT
    # one success, then a full streak of blocks, then a trailing item that must
    # never be reached because the run stops at the streak limit.
    tokens = ["good"] + [f"x{i}" for i in range(limit)] + ["never"]
    df = s.scrape_listings_pages(_listings(*tokens))

    assert list(df["listing_id"]) == ["good"]   # harvest preserved, not discarded
    assert "never" not in scraped               # stopped early at the streak limit
