"""Diagnostic: can we reach Yad2 listing data, and with which technique?

Run locally (residential IP) or in CI to see exactly where the block happens.
    python scripts/diagnose_access.py

It tries, in order of increasing effort:
  1. Plain GET (mirrors the current scraper)
  2. requests.Session with full Chrome headers + homepage warm-up (collect cookies)
  3. The gw.yad2.co.il JSON gateway API
  4. curl_cffi Chrome TLS-fingerprint impersonation (if installed)

For each it prints the HTTP status and classifies the body as BLOCKED /
NO-DATA / OK, so you can tell an IP-reputation block apart from a structural
change to the page.
"""
import json
import sys

import requests

SEARCH_URL = "https://www.yad2.co.il/realestate/rent"
GW_URL = "https://gw.yad2.co.il/realestate-feed/rent/map"
HOME_URL = "https://www.yad2.co.il"
PARAMS = {"city": "6400", "minRooms": "3", "maxRooms": "4.5"}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
    "DNT": "1",
}


def classify(status, text):
    """BLOCKED = WAF challenge, NO-DATA = 200 but no listings, OK = data present."""
    lowered = text[:5000].lower()
    if status == 403 or "transaction id" in lowered or "403 forbidden" in lowered:
        return "BLOCKED (WAF/anti-bot)"
    if "__next_data__" in lowered:
        return "OK (found __NEXT_DATA__ blob)"
    if lowered.strip().startswith("{") or '"data"' in lowered or '"feed"' in lowered:
        return "OK (looks like JSON data)"
    if status == 200:
        return "NO-DATA (200 but no __NEXT_DATA__ / feed — structure changed or JS challenge)"
    return f"UNKNOWN (status {status})"


def report(label, status, text):
    verdict = classify(status, text)
    print(f"\n[{label}]")
    print(f"  HTTP {status}, {len(text)} bytes")
    print(f"  -> {verdict}")
    return verdict


def main():
    print("=" * 70)
    print("Yad2 access diagnostic")
    print("=" * 70)

    # 1. Plain GET (what the current scraper does)
    try:
        r = requests.get(SEARCH_URL, params=PARAMS, headers=BROWSER_HEADERS, timeout=30)
        report("1. plain GET (search page)", r.status_code, r.text)
    except Exception as e:  # noqa: BLE001 - diagnostic, report anything
        print(f"\n[1. plain GET] ERROR: {e}")

    # 2. Session with homepage warm-up (collect any WAF cookies first)
    try:
        s = requests.Session()
        s.headers.update(BROWSER_HEADERS)
        s.get(HOME_URL, timeout=30)  # warm-up: pick up cookies
        r = s.get(SEARCH_URL, params=PARAMS, headers={"Referer": HOME_URL}, timeout=30)
        report("2. session + homepage warm-up", r.status_code, r.text)
    except Exception as e:  # noqa: BLE001
        print(f"\n[2. session warm-up] ERROR: {e}")

    # 3. gw.yad2.co.il JSON gateway API
    try:
        api_headers = {
            **BROWSER_HEADERS,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.yad2.co.il/",
            "Origin": "https://www.yad2.co.il",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
        r = requests.get(GW_URL, params=PARAMS, headers=api_headers, timeout=30)
        report("3. gw.yad2.co.il JSON API", r.status_code, r.text)
    except Exception as e:  # noqa: BLE001
        print(f"\n[3. gw JSON API] ERROR: {e}")

    # 4. curl_cffi TLS-fingerprint impersonation (optional dependency)
    try:
        from curl_cffi import requests as cffi  # type: ignore

        r = cffi.get(SEARCH_URL, params=PARAMS, impersonate="chrome", timeout=30)
        report("4. curl_cffi impersonate=chrome (search page)", r.status_code, r.text)
        r = cffi.get(GW_URL, params=PARAMS, impersonate="chrome", timeout=30)
        report("4b. curl_cffi impersonate=chrome (gw API)", r.status_code, r.text)
    except ImportError:
        print("\n[4. curl_cffi] SKIPPED — not installed. Try: pip install curl_cffi")
    except Exception as e:  # noqa: BLE001
        print(f"\n[4. curl_cffi] ERROR: {e}")

    print("\n" + "=" * 70)
    print("Read the verdicts above:")
    print("  BLOCKED on all  -> IP/fingerprint blocked. Needs proxy or curl_cffi.")
    print("  BLOCKED plain but OK on curl_cffi -> TLS-fingerprint block; use curl_cffi.")
    print("  NO-DATA (200)   -> not blocked, but page structure changed (no __NEXT_DATA__).")
    print("  OK on gw API    -> switch the scraper to the JSON gateway endpoint.")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main())
