"""Browser-based fetching for Madlan (patchright / Playwright stealth).

Madlan is behind PerimeterX (HUMAN) + Cloudflare. Two things Yad2 didn't need:
  1. A *headless* browser is flagged by fingerprint even from a residential IP,
     so we default to HEADFUL with real Chrome (channel="chrome").
  2. PerimeterX may show a one-time "press & hold" challenge. We use a PERSISTENT
     browser profile (user_data_dir) so the clearing cookie (_px3/_pxvid) is kept
     across runs — solve it once in a headful run and later runs reuse it.

MUST run from a residential IP (same as Yad2 — datacenter/CI IPs are hard-blocked).
Set MADLAN_PROXY for a residential proxy if not on a home connection.

To reduce how often the challenge fires, the session warms up on the homepage
first (so PX sets its clearing cookie before we hit deep filtered URLs cold).
When the challenge still appears AND the run is interactive (headful + a TTY),
we pause so YOU can press & hold in the visible window, then continue — the
persistent profile caches the cleared cookie so later runs rarely re-challenge.
We do NOT script the press & hold (that would be circumventing the human check).

Env knobs:
    MADLAN_HEADFUL=0     run headless (only works once the profile is warmed)
    MADLAN_PROFILE_DIR   persistent profile path (default data/.madlan_profile)
    MADLAN_PROXY         residential proxy, e.g. http://user:pass@host:port
    MADLAN_INTERACTIVE=0 never pause for a human to solve the PX challenge
"""
import os
import sys
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


def _search_pois_from(obj):
    """Recursively pull every searchPoiV2.poi item out of a GraphQL JSON response
    (the app's 'load more' calls return {..searchPoiV2:{poi:[...]}}). Bounded by
    the small size of these API payloads."""
    out = []
    if isinstance(obj, dict):
        sp = obj.get("searchPoiV2")
        if isinstance(sp, dict) and isinstance(sp.get("poi"), list):
            out.extend(sp["poi"])
        for v in obj.values():
            out.extend(_search_pois_from(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_search_pois_from(v))
    return out


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
        self._warmed = False

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

    def _interactive(self):
        """A human can solve the press & hold only in a headful, TTY-attached run.
        Off by default under launchd/cron (no TTY) or MADLAN_INTERACTIVE=0."""
        return (self._headful
                and os.getenv("MADLAN_INTERACTIVE", "1") != "0"
                and sys.stdin is not None and sys.stdin.isatty())

    def _warm_up(self):
        """Load the homepage once so PerimeterX collects sensor data and sets its
        clearing cookie in the (persistent) context BEFORE we hit a deep filtered
        URL cold — a cold deep-link is far likelier to trigger the press & hold."""
        if self._warmed:
            return
        self._warmed = True
        # If a prior run already cleared PX, the persistent profile holds the
        # _px3/_pxvid cookie — skip the homepage nav (an extra PX surface that can
        # re-trigger the challenge) and go straight to the target URL.
        try:
            names = {c.get("name") for c in self._ctx.cookies("https://www.madlan.co.il")}
            if "_px3" in names or "_pxvid" in names:
                print("  ↩︎ Madlan: reusing cleared PX cookie from profile; skipping warm-up")
                return
        except Exception:
            pass
        page = self._ctx.new_page()
        try:
            page.goto("https://www.madlan.co.il/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            self._solve_if_blocked(page, "homepage")
            try:
                page.mouse.move(400, 300)
                page.mouse.wheel(0, 1400)
            except Exception:
                pass
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  ⚠️ Madlan homepage warm-up error: {e}")
        finally:
            page.close()

    def _solve_if_blocked(self, page, label):
        """If `page` shows the PX challenge and the run is interactive, pause for
        the human to press & hold in the visible window, then continue. Returns
        True if the page ends up unblocked. No-op (returns current state) when
        non-interactive — we never solve the challenge programmatically."""
        for attempt in range(1, 4):
            if not _looks_blocked(0, page.content()):
                return True
            if not self._interactive():
                return False
            print(f"\n🛑 Madlan PerimeterX challenge on {label}. In the open Chrome "
                  f"window, PRESS & HOLD the button until it clears, then press "
                  f"ENTER here to continue (attempt {attempt}/3)...")
            try:
                input()
            except EOFError:
                return False
            page.wait_for_timeout(2500)
        return not _looks_blocked(0, page.content())

    def fetch(self, url, wait_until="domcontentloaded", timeout=60, settle=2.0,
              retries=3, retry_wait=6):
        """Navigate to url and return (http_status, rendered_html). Warms up once,
        pauses for an interactive human solve on a block, retries otherwise, and
        re-raises the last navigation error on failure."""
        self._warm_up()
        status, html = 0, ""
        for attempt in range(1, retries + 1):
            page = self._ctx.new_page()
            try:
                resp = page.goto(url, wait_until=wait_until, timeout=int(timeout * 1000))
                status = resp.status if resp else 0
                # Wait for the SSR hydration blob (a real block page never has it).
                try:
                    page.wait_for_function(
                        "() => !!window.__SSR_HYDRATED_CONTEXT__", timeout=15000)
                except Exception:
                    pass
                if settle:
                    page.wait_for_timeout(int(settle * 1000))
                html = page.content()
                if _looks_blocked(status, html) and self._solve_if_blocked(page, url):
                    status, html = 200, page.content()
            except Exception as e:
                page.close()
                if _is_connectivity_error(e):
                    print(f"  ⚠️ connectivity lost ({type(e).__name__}); not retrying")
                    raise
                if attempt >= retries:
                    raise
                print(f"  ⚠️ fetch error ({type(e).__name__}); retrying in "
                      f"{retry_wait}s ({attempt}/{retries})...")
                _time.sleep(retry_wait)
                continue
            page.close()
            if not _looks_blocked(status, html):
                return status, html
            if attempt < retries:
                print(f"  ⚠️ blocked (HTTP {status}); retrying in {retry_wait}s "
                      f"({attempt}/{retries}). If this persists, run headful "
                      f"(MADLAN_HEADFUL=1) once and solve the PX challenge.")
                _time.sleep(retry_wait)
        return status, html

    def fetch_search(self, url, want=200, max_scrolls=40, scroll_pause=1.4,
                     timeout=60, settle=2.0):
        """Fetch a search URL and return (status, html, extra_pois).

        The SSR blob embeds only the first ~15 results; the app loads the rest
        via offset-paginated /api2 GraphQL calls as you scroll. We attach a
        response listener, scroll to trigger those calls, and collect the extra
        `searchPoiV2` pois (same shape as the SSR ones). Degrades to SSR-only
        (extra_pois=[]) when scrolling loads nothing or the search fits one page.
        ponytail: unverified from a datacenter IP (PX-blocked); verify on a
        residential run. Never returns fewer than the SSR page — worst case a no-op."""
        self._warm_up()
        page = self._ctx.new_page()
        collected = {}

        def _on_resp(resp):
            try:
                if "/api2/" not in resp.url:
                    return
                for poi in _search_pois_from(resp.json()):
                    if isinstance(poi, dict) and poi.get("id"):
                        collected[poi["id"]] = poi
            except Exception:
                pass

        page.on("response", _on_resp)
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
            status = resp.status if resp else 0
            try:
                page.wait_for_function("() => !!window.__SSR_HYDRATED_CONTEXT__", timeout=15000)
            except Exception:
                pass
            if settle:
                page.wait_for_timeout(int(settle * 1000))
            html = page.content()
            # PX challenge on the search page: let the human solve it, then re-read.
            if _looks_blocked(status, html) and self._solve_if_blocked(page, url):
                status, html = 200, page.content()
            # Scroll to load more; stop at `want`, or after 3 scrolls with no growth.
            stagnant, last = 0, -1
            for _ in range(max_scrolls):
                if len(collected) >= want:
                    break
                page.mouse.wheel(0, 24000)
                try:
                    page.keyboard.press("End")
                except Exception:
                    pass
                page.wait_for_timeout(int(scroll_pause * 1000))
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass
                if len(collected) == last:
                    stagnant += 1
                    if stagnant >= 3:
                        break
                else:
                    stagnant, last = 0, len(collected)
            return status, html, list(collected.values())
        finally:
            page.close()

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
