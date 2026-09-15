"""Offline tests for BrowserSession.fetch retry behavior.

No browser is launched: BrowserSession.__init__ only checks an engine is
importable, and we monkeypatch _fetch_once / _new_context / time.sleep to drive
the retry loop. Verifies the fail-fast-on-connectivity-loss branch.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import yad2_fetch  # noqa: E402


def _session_with(monkeypatch, exc, counters):
    s = yad2_fetch.BrowserSession()

    def boom(*_a, **_k):
        counters["fetch_once"] += 1
        raise exc

    monkeypatch.setattr(s, "_fetch_once", boom)
    monkeypatch.setattr(s, "_new_context",
                        lambda: counters.__setitem__("new_ctx", counters["new_ctx"] + 1))
    monkeypatch.setattr(yad2_fetch._time, "sleep",
                        lambda *_: counters.__setitem__("sleep", counters["sleep"] + 1))
    return s


def test_connectivity_error_fails_fast_without_retry(monkeypatch):
    counters = {"fetch_once": 0, "new_ctx": 0, "sleep": 0}
    err = Exception("Page.goto: net::ERR_INTERNET_DISCONNECTED at https://x")
    s = _session_with(monkeypatch, err, counters)

    with pytest.raises(Exception) as ei:
        s.fetch("https://x", retries=3, retry_wait=6)

    assert "ERR_INTERNET_DISCONNECTED" in str(ei.value)
    assert counters["fetch_once"] == 1   # bailed on the first attempt
    assert counters["new_ctx"] == 0      # never spun a fresh context
    assert counters["sleep"] == 0        # never waited on backoff


def test_dns_failure_also_fails_fast(monkeypatch):
    counters = {"fetch_once": 0, "new_ctx": 0, "sleep": 0}
    err = Exception("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://x")
    s = _session_with(monkeypatch, err, counters)

    with pytest.raises(Exception):
        s.fetch("https://x", retries=3, retry_wait=6)
    assert counters["fetch_once"] == 1
    assert counters["sleep"] == 0


def test_generic_error_still_retries(monkeypatch):
    counters = {"fetch_once": 0, "new_ctx": 0, "sleep": 0}
    err = Exception("Page.goto: Timeout 45000ms exceeded")
    s = _session_with(monkeypatch, err, counters)

    with pytest.raises(Exception):
        s.fetch("https://x", retries=3, retry_wait=6)
    assert counters["fetch_once"] == 3   # exhausted all attempts
    assert counters["sleep"] == 2        # slept between attempts (retries - 1)
