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


def test_jitter_randomizes_wait_within_band(monkeypatch):
    yad2_fetch._random.seed(1234)  # deterministic, so the "varied" check can't flake
    waits = []

    def boom(*_a, **_k):
        raise Exception("Page.goto: Timeout 45000ms exceeded")

    s = yad2_fetch.BrowserSession()
    monkeypatch.setattr(s, "_fetch_once", boom)
    monkeypatch.setattr(s, "_new_context", lambda: None)
    monkeypatch.setattr(yad2_fetch._time, "sleep", waits.append)

    with pytest.raises(Exception):
        s.fetch("https://x", retries=4, retry_wait=6, jitter=0.5)

    assert len(waits) == 3                      # retries - 1 backoff waits
    assert all(3.0 <= w <= 9.0 for w in waits)  # retry_wait × [1-j, 1+j]
    assert len(set(waits)) > 1                  # actually jittered, not constant


def test_no_jitter_keeps_fixed_wait(monkeypatch):
    waits = []

    def boom(*_a, **_k):
        raise Exception("Page.goto: Timeout 45000ms exceeded")

    s = yad2_fetch.BrowserSession()
    monkeypatch.setattr(s, "_fetch_once", boom)
    monkeypatch.setattr(s, "_new_context", lambda: None)
    monkeypatch.setattr(yad2_fetch._time, "sleep", waits.append)

    with pytest.raises(Exception):
        s.fetch("https://x", retries=3, retry_wait=6)  # jitter defaults to 0

    assert waits == [6, 6]  # unchanged fixed cadence when jitter is off


class _FakePage:
    def __init__(self, status, html, record):
        self._status, self._html, self._rec = status, html, record

    def goto(self, *_a, **_k):
        return type("Resp", (), {"status": self._status})()

    def content(self):
        return self._html

    def wait_for_selector(self, *_a, **_k):
        self._rec["waited"] = True

    def wait_for_timeout(self, *_a, **_k):
        pass

    def close(self):
        pass


def _fetch_once_with(monkeypatch, status, html):
    rec = {"waited": False}
    s = yad2_fetch.BrowserSession()
    s._ctx = type("Ctx", (), {"new_page": lambda self: _FakePage(status, html, rec)})()
    out = s._fetch_once("https://x", "domcontentloaded", 45, settle=0)
    return out, rec


def test_block_page_short_circuits_without_selector_wait(monkeypatch):
    # A Radware challenge (signature present, no __NEXT_DATA__) must return at
    # once — never pay the 15s #__NEXT_DATA__ wait that can't succeed.
    (status, html), rec = _fetch_once_with(
        monkeypatch, 200, "<title>Radware Bot Manager Captcha</title>")
    assert status == 200
    assert rec["waited"] is False


def test_loaded_page_with_blob_skips_selector_wait(monkeypatch):
    (_status, _html), rec = _fetch_once_with(
        monkeypatch, 200, '<script id="__NEXT_DATA__">{}</script>')
    assert rec["waited"] is False


def test_half_loaded_page_waits_for_blob(monkeypatch):
    # Legit page, blob not in the DOM yet, no block signature → must wait.
    (_status, _html), rec = _fetch_once_with(monkeypatch, 200, "<html>loading…</html>")
    assert rec["waited"] is True
