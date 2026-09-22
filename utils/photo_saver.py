"""Download a property's listing photos to disk.

Yad2 serves images from img.yad2.co.il, which is NOT behind the Radware WAF
that guards the search/item pages — so plain `requests` fetches them fine (no
browser needed). URLs come from parse_item_detail()'s `images` list.
"""
import os
from urllib.parse import urlsplit

import requests

# Same desktop-Chrome UA the browser engine uses; the CDN is lenient but a
# real UA avoids any UA-based edge cases.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def save_property_photos(listing_id, image_urls, base_dir="data/photos"):
    """Download `image_urls` into base_dir/<listing_id>/. Idempotent: files
    that already exist are skipped. Returns the number of files now present."""
    if not listing_id or not image_urls:
        return 0

    out_dir = os.path.join(base_dir, str(listing_id))
    os.makedirs(out_dir, exist_ok=True)

    saved = 0
    for url in image_urls:
        name = os.path.basename(urlsplit(url).path) or f"{saved}.jpg"
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest):
            saved += 1
            continue
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": _UA})
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
            saved += 1
        except Exception as e:
            print(f"  ⚠️ photo download failed ({name}): {e}")
    return saved
