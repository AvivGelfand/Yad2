"""Decisive test: does a REAL headless browser get past Yad2's WAF, and what
data source does the page actually use now (old __NEXT_DATA__ blob, new RSC
stream, or a JSON gateway API)?

Setup (one time):
    pip install playwright
    playwright install chromium

Run:
    python scripts/diagnose_playwright.py
"""
from playwright.sync_api import sync_playwright

SEARCH_URL = (
    "https://www.yad2.co.il/realestate/rent?city=6400&minRooms=3&maxRooms=4.5"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def main():
    api_calls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="he-IL", user_agent=UA)
        page = ctx.new_page()

        def on_response(resp):
            u = resp.url
            if "yad2.co.il" in u and ("gw." in u or "/api" in u or "feed" in u):
                ct = resp.headers.get("content-type", "").split(";")[0]
                api_calls.append((resp.status, ct, u[:150]))

        page.on("response", on_response)

        resp = page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)
        print(f"Main navigation: HTTP {resp.status if resp else '??'}")
        page.wait_for_timeout(3000)

        html = page.content()
        print(f"Page bytes        : {len(html)}")
        print(f"Has __NEXT_DATA__ : {'__NEXT_DATA__' in html}")
        print(f"Has __next_f (RSC): {'__next_f' in html}")
        print(f"Looks blocked/403 : "
              f"{'403 Forbidden' in html or 'Transaction ID' in html}")

        print("\n--- JSON/API calls the page made (status, type, url) ---")
        if api_calls:
            for st, ct, u in api_calls:
                print(f"  {st}  {ct}  {u}")
        else:
            print("  (none captured — data is likely inlined in the HTML)")

        browser.close()


if __name__ == "__main__":
    main()
