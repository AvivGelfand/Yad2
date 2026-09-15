"""Regression tests for building-shelter detection (מקלט בבניין).

Bug: property 4g5xtp8g had Yad2's structured `inProperty.includeBuildingShelter
= True` but no private safe-room and no free-text "מקלט", so it was reported as
having no shelter. parse_item_detail now surfaces the flag as `shelter`, and the
Telegram message treats the flag (or a free-text mention) as "מקלט בבניין".
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yad2_parse as yp  # noqa: E402
from notifications.telegram_notifier import TelegramNotifier  # noqa: E402


def _item(**in_prop):
    return {
        "token": "shelter1",
        "address": {"city": {"text": "הרצליה"}},
        "additionalDetails": {"roomsCount": 3},
        "inProperty": in_prop,
    }


def _protection_line(property_data):
    n = TelegramNotifier.__new__(TelegramNotifier)  # skip API-pinging __init__
    for line in n.format_property_message(property_data).splitlines():
        if "מרחב מוגן" in line:
            return line
    return ""


def test_parse_surfaces_building_shelter_flag():
    p = yp.parse_item_detail(_item(includeBuildingShelter=True,
                                   includeSecurityRoom=False))
    assert p["shelter"] is True
    assert p["mamad"] is False


def test_building_shelter_flag_reported_as_shelter():
    # The reported bug: flag True, no ממ״ד, no free text -> "מקלט בבניין".
    line = _protection_line({"shelter": True, "mamad": False})
    assert "מקלט בבניין" in line
    assert "אין" not in line


def test_mamad_takes_precedence_over_shelter():
    line = _protection_line({"mamad": True, "shelter": True})
    assert "ממ" in line and "מקלט בבניין" not in line


def test_free_text_shelter_still_detected_without_flag():
    line = _protection_line({"mamad": False, "shelter": None,
                             "description": "דירה עם מקלט בבניין"})
    assert "מקלט בבניין" in line


def test_no_protection_when_flag_false_and_no_text():
    line = _protection_line({"mamad": False, "shelter": False, "description": ""})
    assert "אין" in line
