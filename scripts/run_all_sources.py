"""Combined entry point: scrape Yad2 + Madlan, cross-source dedupe, persist.

This is the multi-source counterpart of scripts/main.py (which is Yad2-only).
main.py is left untouched; switch your launchd/cron to this file to include
Madlan. Flow:

  1. Yad2  -> Yad2MultiSearchScraper.run_multi_search()  (sends Yad2 notifications)
  2. Madlan -> MadlanScraper.run()                        (isolated; a Madlan
     failure/block never aborts the Yad2 result)
  3. combine_and_dedupe([yad2, madlan]) -> tags cross-source duplicates
  4. upsert the combined, deduped frame to Google Sheets + rebuild the gallery
  5. notify Madlan-only NEW listings (a flat already on Yad2 was announced in
     step 1, so cross-source duplicates are skipped — the whole point of dedup)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from config.settings import settings
from config.search_configs import SEARCH_CONFIGURATIONS
from notifications.telegram_notifier import TelegramNotifier
from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter
from utils.dedup import combine_and_dedupe
from utils.property_tracker import PropertyTracker

from scripts.scraper import Yad2MultiSearchScraper
from scripts.madlan_scraper import MadlanScraper
from scripts.build_gallery import main as build_gallery


def _tag_source(df, source):
    if df is not None and not df.empty and "source" not in df.columns:
        df = df.copy()
        df["source"] = source
    return df


def scrape_yad2():
    scraper = Yad2MultiSearchScraper(SEARCH_CONFIGURATIONS, enable_notifications=True)
    return _tag_source(scraper.run_multi_search(), "yad2")


def scrape_madlan():
    """Never let Madlan (block / new-site quirk) break the Yad2 pipeline."""
    try:
        return MadlanScraper().run()
    except Exception as e:
        print(f"⚠️ Madlan scrape failed ({type(e).__name__}: {e}); continuing Yad2-only")
        return pd.DataFrame()


def notify_madlan_only(combined):
    """Notify NEW Madlan listings that are NOT also on Yad2 (those were announced
    by the Yad2 run) and not previously seen. Reuses the shared tracker/notifier."""
    if combined.empty or not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    if not settings.notify_on_new_properties:
        return
    madlan_only = combined[
        (combined["source"] == "madlan")
        & (combined["dup_sources"].apply(lambda s: set(s) == {"madlan"}))
    ]
    if madlan_only.empty:
        return
    tracker = PropertyTracker(settings.database_path)
    try:
        notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    except Exception as e:
        print(f"⚠️ Telegram unavailable for Madlan notifications: {e}")
        return
    sent = 0
    for _, row in madlan_only.iterrows():
        rid = str(row["listing_id"])
        if tracker.property_exists(rid):
            continue
        data = row.to_dict()
        if notifier.should_notify(data) and notifier.send_message(
                notifier.format_property_message(data)):
            sent += 1
        tracker.add_property(rid, data)
    print(f"📱 Sent {sent} Madlan-only notifications")


def main():
    yad2_df = scrape_yad2()
    print(f"\n📥 Yad2: {0 if yad2_df is None else len(yad2_df)} rows")
    madlan_df = scrape_madlan()
    print(f"📥 Madlan: {len(madlan_df)} rows")

    combined = combine_and_dedupe([yad2_df, madlan_df])
    if combined.empty:
        print("No listings from any source")
        return 1

    cross = combined[combined["dup_sources"].apply(lambda s: len(set(s)) > 1)]
    print(f"\n🔗 {len(combined)} total rows; "
          f"{combined['dup_group_id'].nunique()} unique properties; "
          f"{cross['listing_id'].nunique()} listings shared across Yad2+Madlan")

    sheets = GoogleSheetsReaderWriter()
    stats = sheets.upsert_listings(combined, "listing_id")
    print(f"✅ Sheets: {stats.get('new')} new / {stats.get('updated')} updated")

    notify_madlan_only(combined)

    try:
        build_gallery()
    except Exception as e:
        print(f"⚠️ Gallery rebuild skipped: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
