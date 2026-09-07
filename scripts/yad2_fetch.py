"""Browser-based fetching for Yad2 (patchright / Playwright stealth).

Yad2 is behind Radware Bot Manager: plain HTTP clients (requests, curl_cffi,
httpx) get a 403/challenge even from a residential IP because they never
execute the JS challenge that mints the access cookie. A real browser engine
does. patchright is a stealth-patched Playwright drop-in; we fall back to plain
playwright if patchright is not installed.

MUST run from a residential IP. Datacenter / CI IPs (including GitHub-hosted
runners) are ASN-blocked by Radware regardless of the browser — use a
self-hosted runner on a home connection or an Israeli residential proxy.

Setup:  pip install patchright  &&  patchright install chromium
"""
import os
import time as _time
from urllib.parse import urlsplit

try:
    import yad2_parse as _yp  # sibling module; used for block detection on retry
except ImportError:  # pragma: no cover
    _yp = None


def _proxy_from_env():
    """Build a Playwright proxy dict from env, or None. Set YAD2_PROXY to a
    residential proxy (e.g. http://user:pass@host:port or http://host:port);
    creds may also be given via YAD2_PROXY_USERNAME / YAD2_PROXY_PASSWORD.

    Required to scrape from a datacenter/CI IP — GitHub-hosted runners are
    hard-blocked by Radware Bot Manager regardless of the browser."""
    raw = os.getenv("YAD2_PROXY")
    if not raw:
        return None
    parts = urlsplit(raw if "://" in raw else f"http://{raw}")
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    proxy = {"server": f"{parts.scheme or 'http'}://{netloc}"}
    user = os.getenv("YAD2_PROXY_USERNAME") or parts.username
    password = os.getenv("YAD2_PROXY_PASSWORD") or parts.password
    if user:
        proxy["username"] = user
    if password:
        proxy["password"] = password
    return proxy

try:
    from patchright.sync_api import sync_playwright
    ENGINE = "patchright"
except ImportError:  # pragma: no cover - depends on what's installed
    try:
        from playwright.sync_api import sync_playwright
        ENGINE = "playwright"
    except ImportError:
        sync_playwright = None
        ENGINE = None

# A clean desktop-Chrome UA. NOT the default headless UA — its "HeadlessChrome"
# token is auto-blocked and bounces the request to validate.perfdrive.com.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _require_engine():
    if sync_playwright is None:
        raise RuntimeError(
            "No browser engine installed. Run: pip install patchright && "
            "patchright install chromium"
        )


def _looks_blocked(status, html):
    if _yp is not None:
        return _yp.is_blocked(html, status)
    # Minimal fallback if yad2_parse isn't importable.
    if status in (401, 403, 429):
        return True
    return "__NEXT_DATA__" not in (html or "")


class BrowserSession:
    """A reusable headless browser. Use ONE instance per scraper run — launching
    a fresh browser for every page/item would be far too slow and hammers the
    WAF. Use as a context manager:

        with BrowserSession() as s:
            status, html = s.fetch(url)
    """

    def __init__(self, headless=True, channel="chrome", proxy=None):
        _require_engine()
        self._headless = headless
        self._channel = channel
        # Explicit proxy dict wins; otherwise read YAD2_PROXY from the env.
        self._proxy = proxy if proxy is not None else _proxy_from_env()
        self._pw = self._browser = self._ctx = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        try:
            # Real Chrome (channel="chrome") is the least detectable if present.
            self._browser = self._pw.chromium.launch(
                headless=self._headless, channel=self._channel
            )
        except Exception:
            self._browser = self._pw.chromium.launch(headless=self._headless)
        self._new_context()
        return self

    def _new_context(self):
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:
                pass
        ctx_kwargs = dict(
            locale="he-IL",
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
        )
        if self._proxy:
            ctx_kwargs["proxy"] = self._proxy
        self._ctx = self._browser.new_context(**ctx_kwargs)

    def _fetch_once(self, url, wait_until, timeout, settle):
        page = self._ctx.new_page()
        try:
            resp = page.goto(url, wait_until=wait_until, timeout=int(timeout * 1000))
            if settle:
                page.wait_for_timeout(int(settle * 1000))
            return (resp.status if resp else 0, page.content())
        finally:
            page.close()

    def fetch(self, url, wait_until="networkidle", timeout=60, settle=2.0,
              retries=3, retry_wait=6):
        """Navigate to url and return (http_status, rendered_html).

        On an anti-bot block, retry with a FRESH browser context (a fresh
        context/session often clears the challenge — the first request after a
        reset tends to succeed) up to `retries` times with a delay between."""
        status, html = 0, ""
        for attempt in range(1, retries + 1):
            status, html = self._fetch_once(url, wait_until, timeout, settle)
            if not _looks_blocked(status, html):
                return status, html
            if attempt < retries:
                print(f"  ⚠️ blocked (HTTP {status}); retrying with a fresh "
                      f"context in {retry_wait}s ({attempt}/{retries})...")
                self._new_context()
                _time.sleep(retry_wait)
        return status, html

    def __exit__(self, *exc):
        for obj, meth in (
            (self._ctx, "close"),
            (self._browser, "close"),
            (self._pw, "stop"),
        ):
            try:
                if obj:
                    getattr(obj, meth)()
            except Exception:
                pass


def fetch_page(url, timeout=60, headless=True):
    """One-shot fetch (spins up and tears down a browser). Handy for probes;
    the scraper uses a long-lived BrowserSession instead."""
    with BrowserSession(headless=headless) as session:
        return session.fetch(url, timeout=timeout)
