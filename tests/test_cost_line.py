"""Tests for the Telegram rent line: base rent + ועד + ארנונה + monthly total."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notifications.telegram_notifier import TelegramNotifier  # noqa: E402


def _rent_line(property_data):
    n = TelegramNotifier.__new__(TelegramNotifier)  # skip API-pinging __init__
    for line in n.format_property_message(property_data).splitlines():
        if "Rent:" in line:
            return line
    return ""


def test_rent_with_vaad_and_arnona_shows_all_plus_total():
    line = _rent_line({"rent": 7500, "vaad": 240, "arnona_month": 1220})
    assert "₪7,500" in line
    assert "ועד ₪240" in line
    assert "ארנונה ₪1,220" in line
    assert "₪8,960" in line  # 7500 + 240 + 1220, monthly total


def test_rent_only_no_fees_no_total():
    line = _rent_line({"rent": 8000, "vaad": None, "arnona_month": None})
    assert "₪8,000" in line
    assert "ועד" not in line and "ארנונה" not in line and "סה" not in line


def test_partial_fees_total_sums_present_only():
    line = _rent_line({"rent": 5000, "vaad": 300, "arnona_month": None})
    assert "ועד ₪300" in line and "ארנונה" not in line
    assert "₪5,300" in line  # total = rent + vaad


def test_nan_and_string_fees_coerced():
    # pandas rows deliver NaN for missing; scrapers may deliver "1,100".
    line = _rent_line({"rent": "6,000", "vaad": float("nan"), "arnona_month": "1,100"})
    assert "₪6,000" in line
    assert "ועד" not in line               # NaN vaad dropped
    assert "ארנונה ₪1,100" in line
    assert "₪7,100" in line                # 6000 + 1100


def test_missing_price_still_safe():
    line = _rent_line({"rent": None, "vaad": 240, "arnona_month": 1220})
    assert "Price not specified" in line
