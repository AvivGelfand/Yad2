"""Browser-based fetching for Madlan (patchright / Playwright stealth).

Madlan is behind PerimeterX (HUMAN) + Cloudflare. Two things Yad2 didn't need:
  1. A *headless* browser is flagged by fingerprint even from a residential IP,
     so we default to HEADFUL with real Chrome (channel="chrome").
  2. PerimeterX may show a one-time "press & hold" challenge. We use a PERSISTENT
     browser profile (user_data_dir) so the clearing cookie (_px3/_pxvid) is kept
     across runs — solve it once in a headful run and later runs reuse it.

MUST run from a residential IP (same as Yad2 — datacenter/CI IPs are hard-blocked).
Set MADLAN_PROXY for a residential proxy if not on a home connection.

Env knobs:
    MADLAN_HEADFUL=0     run headless (only works once the profile is warmed)
    MADLAN_PROFILE_DIR   persistent profile path (default data/.madlan_profile)
    MADLAN_PROXY         residential proxy, e.g. http://user:pass@host:port
"""
import os
import time as _time
from urllib.parse import urlsplit

try:
    import madlan_parse as _mp  # sibling module; block detection on retry
except ImportError:  # pragma: no cover
    _mp = None

try:
    from patchright.sync_api import sync_playwright
    ENGINE = "patchright"
except ImportError:  # pragma: no cover
    try:
        from playwright.sync_api import sync_playwright
        ENGINE = "playwright"
    except ImportError:
        sync_playwright = None
        ENGINE = None

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_CONNECTIVITY_ERRORS = (
    "ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED",
    "ERR_NETWORK_CHANGED", "ERR_ADDRESS_UNREACHABLE",
    "ERR_PROXY_CONNECTION_FAILED",
)


def _require_engine():
    if sync_playwright is None:
        raise RuntimeError(
            "No browser engine installed. Run: pip install patchright && "
            "patchright install chromium"
        )


def _proxy_from_env():
    raw = os.getenv("MADLAN_PROXY")
    if not raw:
        return None
    parts = urlsplit(raw if "://" in raw else f"http://{raw}")
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    proxy = {"server": f"{parts.scheme or 'http'}://{netloc}"}
    user = os.getenv("MADLAN_PROXY_USERNAME") or parts.username
    password = os.getenv("MADLAN_PROXY_PASSWORD") or parts.password
    if user:
        proxy["username"] = user
    if password:
        proxy["password"] = password
    return proxy


def _looks_blocked(status, html):
    if _mp is not None:
        return _mp.is_blocked(html, status)
    if status in (401, 403, 429):
        return True
    return "window.__SSR_HYDRATED_CONTEXT__" not in (html or "")


def _is_connectivity_error(exc):
    return any(sig in str(exc) for sig in _CONNECTIVITY_ERRORS)


class MadlanSession:
    """A reusable headful Chrome with a persistent PerimeterX-cleared profile.
    Use ONE instance per run (context manager):

        with MadlanSession() as s:
            status, html = s.fetch(url)
    """

    def __init__(self, headful=None, proxy=None, profile_dir=None):
        _require_engine()
        self._headful = (os.getenv("MADLAN_HEADFUL", "1") != "0"
                         if headful is None else headful)
        self._proxy = proxy if proxy is not None else _proxy_from_env()
        self._profile_dir = profile_dir or os.getenv(
            "MADLAN_PROFILE_DIR",
            os.path.join(os.path.dirname(__file__), "..", "data", ".madlan_profile"),
        )
        self._pw = self._ctx = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        os.makedirs(self._profile_dir, exist_ok=True)
        kwargs = dict(
            user_data_dir=self._profile_dir,
            headless=not self._headful,
            locale="he-IL",
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
        )
        if self._proxy:
            kwargs["proxy"] = self._proxy
        # Persistent context = the profile (and its PX cookies) survives runs.
        # Real Chrome is far less detectable than bundled chromium.
        try:
            self._ctx = self._pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
        except Exception:
            self._ctx = self._pw.chromium.launch_persistent_context(**kwargs)
        return self

    def _fetch_once(self, url, wait_until, timeout, settle):
        page = self._ctx.new_page()
        try:
            resp = page.goto(url, wait_until=wait_until, timeout=int(timeout * 1000))
            # Wait for the SSR hydration blob to land in the DOM (a real block
            # page never has it, so the timeout is harmless there).
            try:
                page.wait_for_function(
                    "() => !!window.__SSR_HYDRATED_CONTEXT__", timeout=15000
                )
            except Exception:
                pass
            if settle:
                page.wait_for_timeout(int(settle * 1000))
            return (resp.status if resp else 0, page.content())
        finally:
            page.close()

    def fetch(self, url, wait_until="domcontentloaded", timeout=60, settle=2.0,
              retries=3, retry_wait=6):
        """Navigate to url and return (http_status, rendered_html). Retries on a
        block or navigation error; re-raises the last navigation error on failure."""
        status, html = 0, ""
        for attempt in range(1, retries + 1):
            try:
                status, html = self._fetch_once(url, wait_until, timeout, settle)
            except Exception as e:
                if _is_connectivity_error(e):
                    print(f"  ⚠️ connectivity lost ({type(e).__name__}); not retrying")
                    raise
                if attempt >= retries:
                    raise
                print(f"  ⚠️ fetch error ({type(e).__name__}); retrying in "
                      f"{retry_wait}s ({attempt}/{retries})...")
                _time.sleep(retry_wait)
                continue
            if not _looks_blocked(status, html):
                return status, html
            if attempt < retries:
                print(f"  ⚠️ blocked (HTTP {status}); retrying in {retry_wait}s "
                      f"({attempt}/{retries}). If this persists, run headful "
                      f"(MADLAN_HEADFUL=1) once to solve the PX challenge.")
                _time.sleep(retry_wait)
        return status, html

    def __exit__(self, *exc):
        for obj, meth in ((self._ctx, "close"), (self._pw, "stop")):
            try:
                if obj:
                    getattr(obj, meth)()
            except Exception:
                pass


def fetch_page(url, timeout=60, headful=None):
    """One-shot fetch (spins up and tears down a browser). Handy for probes."""
    with MadlanSession(headful=headful) as session:
        return session.fetch(url, timeout=timeout)
