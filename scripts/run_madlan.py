"""Madlan-only scheduled entry point — the separate-cadence counterpart of
scripts/main.py (which is Yad2-only).

Runs on its OWN launchd job (deploy/com.yad2.madlan.plist), writes to its OWN
'Madlan' worksheet tab, and only ever READS the Yad2 'Properties' tab (for
cross-source dedup). It never writes 'Properties', so a Madlan block/failure
cannot lose or corrupt Yad2 data — the two runs share no writable sheet state.

Flow:
  1. Madlan -> MadlanScraper.run()  (isolated; empty frame on any failure)
  2. read the Yad2 'Properties' tab (read-only) -> cross-source dedupe, so a flat
     already announced by the Yad2 run isn't notified again
  3. upsert Madlan rows to the 'Madlan' tab (created on first run if missing)
  4. notify Madlan-only NEW listings (shared tracker + notifier)
  5. heartbeat: track consecutive zero-result runs; when Madlan returns nothing
     for N runs in a row the PerimeterX cookie has likely lapsed -> one Telegram
     alert telling you to re-solve the challenge once, interactively.

Manual re-solve (when you get the alert): run once from a terminal so a window
opens and you can press & hold — the cleared cookie then lets the headless
launchd runs work again:
    MADLAN_HEADFUL=1 <python> scripts/run_madlan.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from config.settings import settings
from notifications.telegram_notifier import TelegramNotifier
from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter
from utils.dedup import combine_and_dedupe
from utils.property_tracker import PropertyTracker

from scripts.madlan_scraper import MadlanScraper

MADLAN_WORKSHEET = os.getenv("MADLAN_WORKSHEET", "Madlan")
# Consecutive zero-result runs before we alert that the PX cookie likely lapsed.
ZERO_STREAK_ALERT = int(os.getenv("MADLAN_ZERO_STREAK_ALERT", "3"))
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", ".madlan_state.json")


def scrape_madlan():
    """Never let a Madlan block/quirk raise out of this run."""
    try:
        return MadlanScraper().run()
    except Exception as e:
        print(f"⚠️ Madlan scrape failed ({type(e).__name__}: {e})")
        return pd.DataFrame()


def _telegram():
    """A TelegramNotifier, or None when creds are absent/placeholder/invalid."""
    token, chat = settings.telegram_bot_token, settings.telegram_chat_id
    if not token or not chat or token == "YOUR_BOT_TOKEN" or chat == "YOUR_CHAT_ID":
        return None
    try:
        return TelegramNotifier(token, chat)
    except Exception as e:
        print(f"⚠️ Telegram unavailable: {e}")
        return None


def _load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def heartbeat(n_rows, notifier):
    """Track the consecutive-zero-result streak and alert ONCE when it crosses
    the threshold (a lapsed PerimeterX cookie is the usual cause). Any non-zero
    run resets the streak and the alert latch."""
    state = _load_state()
    if n_rows > 0:
        if state.get("zero_streak"):
            print(f"✅ Madlan recovered after {state['zero_streak']} empty run(s)")
        _save_state({"zero_streak": 0, "alerted": False})
        return
    streak = state.get("zero_streak", 0) + 1
    alerted = state.get("alerted", False)
    if streak >= ZERO_STREAK_ALERT and not alerted and notifier:
        notifier.send_message(
            f"🟠 Madlan scraper: 0 listings for {streak} runs in a row.\n"
            "The PerimeterX cookie has likely expired. Re-solve it once, "
            "interactively, then headless runs resume:\n"
            "MADLAN_HEADFUL=1 python scripts/run_madlan.py"
        )
        alerted = True
    _save_state({"zero_streak": streak, "alerted": alerted})
    print(f"⚠️ Madlan empty run (streak {streak}/{ZERO_STREAK_ALERT})")


def cross_source_ids(madlan_df):
    """listing_ids of Madlan flats that are ALSO on Yad2 (already announced by the
    Yad2 run) — skip notifying those. Best-effort: any failure reading/ deduping
    the Yad2 sheet just yields an empty set (notify all, no crash)."""
    try:
        yad2 = GoogleSheetsReaderWriter().read_sheet_as_dataframe()
        if yad2.empty:
            return set()
        yad2 = yad2.copy()
        yad2["source"] = "yad2"
        combined = combine_and_dedupe([yad2, madlan_df])
        cross = combined[
            (combined["source"] == "madlan")
            & (combined["dup_sources"].apply(lambda s: "yad2" in set(s)))
        ]
        return set(cross["listing_id"].astype(str))
    except Exception as e:
        print(f"⚠️ cross-source dedup skipped ({type(e).__name__}: {e})")
        return set()


def write_madlan_tab(madlan_df):
    """Upsert Madlan rows into the dedicated 'Madlan' tab (never 'Properties')."""
    sheets = GoogleSheetsReaderWriter(worksheet_name=MADLAN_WORKSHEET)
    sheets._ensure_archive_sheet_exists(MADLAN_WORKSHEET)  # create tab if missing
    stats = sheets.upsert_listings(madlan_df, "listing_id")
    print(f"✅ Madlan tab: {stats.get('new')} new / {stats.get('updated')} updated")


def notify_new(madlan_df, cross_ids, notifier):
    """Notify NEW Madlan-only listings (not on Yad2, not already seen)."""
    if notifier is None or not settings.notify_on_new_properties:
        return
    tracker = PropertyTracker(settings.database_path)
    sent = 0
    for _, row in madlan_df.iterrows():
        rid = str(row["listing_id"])
        if rid in cross_ids or tracker.property_exists(rid):
            continue
        data = row.to_dict()
        if notifier.should_notify(data) and notifier.send_message(
                notifier.format_property_message(data)):
            sent += 1
        tracker.add_property(rid, data)
    print(f"📱 Sent {sent} Madlan-only notifications")


def main():
    madlan_df = scrape_madlan()
    n = len(madlan_df)
    print(f"📥 Madlan: {n} rows")

    notifier = _telegram()
    heartbeat(n, notifier)
    if n == 0:
        return 0

    cross_ids = cross_source_ids(madlan_df)
    write_madlan_tab(madlan_df)
    notify_new(madlan_df, cross_ids, notifier)
    return 0


if __name__ == "__main__":
    sys.exit(main())
