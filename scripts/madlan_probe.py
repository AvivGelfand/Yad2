"""One-shot Madlan recon — run this ONCE on your Mac (residential IP).

madlan.co.il is behind PerimeterX (App ID o4wPDYYd) + Cloudflare. A *headless*
browser gets flagged by fingerprint even from a residential IP, so this runs
HEADFUL with your real Chrome and lets you solve the one-time "press & hold"
challenge in the visible window if it appears. Once past it, it records WHERE
the listing data lives (embedded __NEXT_DATA__ / __APOLLO_STATE__, or the /api2
GraphQL XHR) and saves fixtures so `madlan_parse.py` can be finalized against
real data — exactly how the Yad2 parser was built from its __NEXT_DATA__ fixtures.

Usage (from the repo root, on your Mac):
    /Users/aviv.gelfand@gong.io/miniconda3/bin/python \
        .claude/worktrees/madlan-scraper/scripts/madlan_probe.py

Env knobs:
    MADLAN_HEADFUL=0   force headless (default: headful, recommended)
    MADLAN_PROXY=...    route through a proxy (only needed on a blocked IP)

Outputs -> data/madlan_fixtures/: search.html, item.html, *_next_data.json /
*_apollo.json, api_*.json (each /api2 XHR), SUMMARY.txt.
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv  # reads MADLAN_PROXY from the repo's .env
    load_dotenv()
except ImportError:
    pass

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "madlan_fixtures")

SEARCH_URL = ("https://www.madlan.co.il/for-rent/%D7%94%D7%A8%D7%A6%D7%9C%D7%99%D7%94-"
              "%D7%99%D7%A9%D7%A8%D7%90%D7%9C?filters=_5000-8500_3-4.5____secureRoom"
              "%2Cmamak%2Cmiklat%2Cbalcony%2Celevator_____0-10000_______search-filter-top-bar")
ITEM_URL = "https://www.madlan.co.il/listings/XcM1UBEhHDU?dealType=rent"
# Optional CLI arg: an item id or full listing URL to probe instead of the default
# (e.g. `madlan_probe.py hC1zbsjUN2E`). Saves that item's raw poi to item_poi.json
# and prints its amenities, so a real listing can be captured as a test fixture.
if len(sys.argv) > 1:
    _a = sys.argv[1].strip()
    ITEM_URL = _a if _a.startswith("http") else f"https://www.madlan.co.il/listings/{_a}?dealType=rent"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

try:
    from patchright.sync_api import sync_playwright
    ENGINE = "patchright"
except ImportError:
    from playwright.sync_api import sync_playwright
    ENGINE = "playwright"


def _proxy():
    raw = os.getenv("MADLAN_PROXY")
    if not raw:
        return None
    p = urlsplit(raw if "://" in raw else f"http://{raw}")
    netloc = p.hostname + (f":{p.port}" if p.port else "")
    d = {"server": f"{p.scheme or 'http'}://{netloc}"}
    if p.username:
        d["username"] = p.username
    if p.password:
        d["password"] = p.password
    return d


# A real block = a 403/429, OR the interactive PX captcha widget, OR the Hebrew
# "we think you're a robot" text. NOT the mere presence of the PX sensor script
# (`_pxAppId`, client.px-cloud.net) — that runs on EVERY Madlan page, including
# good ones. Embedded listing data short-circuits to "not blocked".
_BLOCK_TEXT = ("px-captcha", "captcha-delivery", "לחשוב שאתה רובוט",
               "press & hold", "press and hold", "לחצו והחזיקו")


def _is_block(status, html):
    if html and ("__NEXT_DATA__" in html or "__APOLLO_STATE__" in html):
        return False
    if status in (403, 429):
        return True
    low = (html or "").lower()
    return any(sig in low or sig in (html or "") for sig in _BLOCK_TEXT)


def _extract_blob(html, key_regex, label):
    m = re.search(key_regex, html, re.DOTALL)
    if not m:
        return None
    raw = m.group(1)
    for candidate in (raw, raw.rstrip(";").strip()):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    print(f"  ! found {label} but could not JSON-parse it")
    return None


def probe(page, url, tag, summary, api_calls):
    print(f"\n=== {tag}: {url[:90]}...")
    resp = page.goto(url, wait_until="domcontentloaded", timeout=90000)
    status = resp.status if resp else 0
    page.wait_for_timeout(6000)

    # If PX shows the challenge, let the human solve it in the visible window.
    for attempt in range(1, 4):
        html = page.content()
        if not _is_block(status, html):
            break
        print(f"  ⚠️ {tag}: looks blocked (HTTP {status}). A challenge is likely "
              f"visible in the Chrome window.\n     → Solve the 'press & hold' / "
              f"CAPTCHA there, then press ENTER here to continue (attempt {attempt}/3)...")
        try:
            input()
        except EOFError:
            break
        page.wait_for_timeout(3000)
        status = 200  # after a manual solve the DOM is what matters, not the old status

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    html = page.content()
    with open(os.path.join(OUT_DIR, f"{tag}.html"), "w") as f:
        f.write(html)

    if _is_block(status, html):
        line = f"{tag}: STILL BLOCKED after manual attempts (HTTP {status})"
        print("  " + line)
        summary.append(line)
        return

    found = []
    nd = _extract_blob(html, r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', "__NEXT_DATA__")
    if nd:
        json.dump(nd, open(os.path.join(OUT_DIR, f"{tag}_next_data.json"), "w"),
                  ensure_ascii=False, indent=2)
        found.append("__NEXT_DATA__")
    ap = _extract_blob(html, r'__APOLLO_STATE__\s*=\s*(\{.*?\})\s*(?:;|</script>)', "__APOLLO_STATE__")
    if ap:
        json.dump(ap, open(os.path.join(OUT_DIR, f"{tag}_apollo.json"), "w"),
                  ensure_ascii=False, indent=2)
        found.append("__APOLLO_STATE__")

    line = (f"{tag}: HTTP {status} OK, {len(html)} bytes; "
            f"embedded=[{', '.join(found) or 'none'}]; api2_xhr_captured={len(api_calls)}")
    print("  " + line)
    summary.append(line)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    headful = os.getenv("MADLAN_HEADFUL", "1") != "0"
    api_calls = []

    with sync_playwright() as pw:
        print(f"engine={ENGINE}  headful={headful}  proxy={'yes' if os.getenv('MADLAN_PROXY') else 'no'}")
        launch = {"headless": not headful}
        proxy = _proxy()
        if proxy:
            launch["proxy"] = proxy
        # Real Chrome (channel='chrome') is far less detectable than bundled chromium.
        try:
            browser = pw.chromium.launch(channel="chrome", **launch)
            print("  launched real Chrome (channel=chrome)")
        except Exception as e:
            print(f"  ! real Chrome unavailable ({e}); using bundled chromium")
            browser = pw.chromium.launch(**launch)
        ctx = browser.new_context(locale="he-IL", user_agent=UA,
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()

        def on_resp(resp):
            u = resp.url
            if "/api2/" in u and "madlan" in u:
                rec = {"status": resp.status, "method": resp.request.method, "url": u,
                       "request_body": resp.request.post_data}
                try:
                    rec["response"] = resp.json()
                except Exception:
                    try:
                        rec["response_text"] = resp.text()[:20000]
                    except Exception:
                        rec["response_text"] = "<unavailable>"
                api_calls.append(rec)
        page.on("response", on_resp)

        summary = []
        # Warm up on the homepage; solving the challenge once here clears the whole session.
        try:
            page.goto("https://www.madlan.co.il/", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            if _is_block(200, page.content()):
                print("\n⚠️ Homepage shows the PX challenge. Solve it in the Chrome "
                      "window, then press ENTER here...")
                try:
                    input()
                except EOFError:
                    pass
            page.mouse.move(400, 300); page.mouse.wheel(0, 1200); page.wait_for_timeout(1500)
        except Exception as e:
            print(f"  ! homepage warm-up error: {e}")

        probe(page, SEARCH_URL, "search", summary, api_calls)
        search_apis = len(api_calls)
        probe(page, ITEM_URL, "item", summary, api_calls)

        # Save the parsed item poi (raw, for use as a test fixture) and print its
        # amenities — the fields (elevator/mamad/shelter/AC) the feed lacks.
        try:
            import madlan_parse as _mp
            ihtml = open(os.path.join(OUT_DIR, "item.html"), encoding="utf-8").read()
            ctx = _mp.extract_ssr_context(ihtml)
            poi = _mp.extract_item_detail(ctx) if ctx else None
            if poi:
                json.dump(poi, open(os.path.join(OUT_DIR, "item_poi.json"), "w"),
                          ensure_ascii=False, indent=1)
                r = _mp.parse_listing(poi)
                line = (f"item {r['listing_id']}: elevator={r['elevator']} "
                        f"mamad={r['mamad']} shelter={r['shelter']} balcony={r['balcony']} "
                        f"AC={r['AC']}  (saved item_poi.json for use as a fixture)")
                print("  " + line)
                summary.append(line)
        except Exception as e:
            print(f"  ! item poi extract failed: {e}")

        for i, rec in enumerate(api_calls):
            json.dump(rec, open(os.path.join(OUT_DIR, f"api_{i:02d}.json"), "w"),
                      ensure_ascii=False, indent=2)

        summary.append(f"\nAPI /api2 XHRs captured: {len(api_calls)} (search phase: {search_apis})")
        for rec in api_calls:
            summary.append(f"  {rec['method']} {rec['status']} {rec['url'][:120]}")

        report = "\n".join(summary)
        with open(os.path.join(OUT_DIR, "SUMMARY.txt"), "w") as f:
            f.write(report + "\n")
        print("\n" + "=" * 60 + "\n" + report + "\n" + "=" * 60)
        print(f"\nFixtures written to {os.path.abspath(OUT_DIR)}")
        print('Reply "done" in the chat — the fixtures are on the same disk, I\'ll read them.')
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
