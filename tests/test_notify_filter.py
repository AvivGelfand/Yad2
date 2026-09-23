"""Notifications are suppressed for listings with no protected space.

should_notify() must return False when a listing has no ממ״ד / מקלט / ממ״ק, so
such apartments are never sent to Telegram (in addition to the existing
blocked-neighborhood rule).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notifications.telegram_notifier import TelegramNotifier  # noqa: E402

notify = TelegramNotifier.should_notify


def test_no_protection_not_notified():
    assert notify({"neighborhood": "מרכז", "mamad": False,
                   "shelter": False, "description": ""}) is False


def test_mamad_notified():
    assert notify({"neighborhood": "מרכז", "mamad": True}) is True


def test_shelter_flag_notified():
    assert notify({"neighborhood": "מרכז", "shelter": True}) is True


def test_mamak_free_text_notified():
    assert notify({"neighborhood": "מרכז", "mamad": False, "shelter": False,
                   "description": "דירה מהממת עם ממ\"ק בקומה"}) is True


def test_miklat_free_text_notified():
    assert notify({"neighborhood": "מרכז", "description": "יש מקלט בבניין"}) is True


def test_blocked_neighborhood_not_notified_even_with_mamad():
    assert notify({"neighborhood": "יד התשעה", "mamad": True}) is False
