"""Regression tests for neighborhood block-listing.

Bug: property dsktsb33 has neighborhood "יד התשעה, שביב" (a compound label:
blocked name + sub-area). should_notify used exact set-membership, so the
compound didn't match "יד התשעה" and a message was sent. It now matches by
substring.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notifications.telegram_notifier import TelegramNotifier as TN  # noqa: E402


def test_compound_neighborhood_is_blocked():
    # The reported bug.
    assert TN.should_notify({"neighborhood": "יד התשעה, שביב"}) is False


def test_exact_blocked_neighborhood_still_blocked():
    assert TN.should_notify({"neighborhood": "יד התשעה"}) is False


def test_blocked_name_in_any_position():
    assert TN.should_notify({"neighborhood": "שביב, יד התשעה"}) is False


def test_gershayim_variant_blocked():
    # block list holds גן רש"ל; a quoted-variant in the data must still match.
    assert TN.should_notify({"neighborhood": 'גן רש"ל, מערב'}) is False


def test_allowed_neighborhood_notifies():
    assert TN.should_notify({"neighborhood": "מרכז"}) is True


def test_missing_neighborhood_notifies():
    assert TN.should_notify({}) is True
    assert TN.should_notify({"neighborhood": None}) is True
