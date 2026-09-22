"""Build a static gallery.html: a one-property-at-a-time viewer. Each property
fills the screen with a big photo carousel (+ thumbnail strip) showing ALL its
pictures, plus its details from the Google Sheet. Navigate between properties
with the ‹ הקודם / הבא › buttons (or ↑/↓); step through a property's photos with
‹ › (or ←/→).

    /opt/conda/bin/python3 scripts/build_gallery.py
    # writes data/gallery.html — open it in a browser

Self-contained output (inline CSS/JS, no framework, no server). Photos are
referenced relatively (photos/<listing_id>/...), so gallery.html must stay in
data/ next to the photos/ dir.
"""
import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PHOTOS_DIR = os.path.join(ROOT, "data", "photos")
OUT = os.path.join(ROOT, "data", "gallery.html")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

# Amenities rendered as chips when truthy.
BOOL_FIELDS = [
    ("elevator", "🛗 מעלית"), ("balcony", "🌿 מרפסת"), ("mamad", "🚀 ממ״ד"),
    ("shelter", "🛡️ מקלט"), ("parking", "🅿️ חניה"), ("AC", "❄️ מיזוג"),
    ("Boiler", "♨️ דוד"), ("renovated", "✨ משופץ"), ("pets", "🐾 חיות"),
]
# Extra detail rows: (column, label).
META_FIELDS = [
    ("property_type", "סוג"), ("condition", "מצב"), ("entry", "כניסה"),
    ("arnona_month", "ארנונה/חודש"), ("vaad", "ועד בית"), ("furniture", "ריהוט"),
    ("total_floors", "קומות בבניין"),
]


def _truthy(v):
    return str(v).strip().upper() in ("TRUE", "1", "YES") or v is True


def _txt(v):
    s = "" if v is None else str(v)
    return html.escape(s).strip()


def _load_sheet_rows():
    """listing_id -> row dict, from the Google Sheet. Empty dict on any failure
    (network/auth) so the gallery still builds from photos alone."""
    try:
        from src.writers.google_sheets_reader_writer import GoogleSheetsReaderWriter
        df = GoogleSheetsReaderWriter().read_sheet_as_dataframe()
        if df.empty or "listing_id" not in df.columns:
            return {}
        return {str(r["listing_id"]): r.to_dict() for _, r in df.iterrows()}
    except Exception as e:
        print(f"⚠️ Could not read Google Sheet ({e}); building photos-only cards.")
        return {}


def _property_folders():
    """(listing_id, [image filenames]) for each folder that has images."""
    out = []
    if not os.path.isdir(PHOTOS_DIR):
        return out
    for lid in sorted(os.listdir(PHOTOS_DIR)):
        d = os.path.join(PHOTOS_DIR, lid)
        if not os.path.isdir(d):
            continue
        imgs = sorted(f for f in os.listdir(d) if f.lower().endswith(IMG_EXT))
        if imgs:
            out.append((lid, imgs))
    return out


def _rent(row):
    try:
        return float(row.get("rent") or 0)
    except (TypeError, ValueError):
        return 0.0


def _carousel(lid, imgs):
    frames = "".join(
        f'<img class="frame{" active" if i == 0 else ""}" loading="lazy" '
        f'src="photos/{html.escape(lid)}/{html.escape(name)}" '
        f'onclick="window.open(this.src)">'
        for i, name in enumerate(imgs)
    )
    thumbs = "".join(
        f'<img class="thumb{" active" if i == 0 else ""}" data-i="{i}" '
        f'loading="lazy" src="photos/{html.escape(lid)}/{html.escape(name)}">'
        for i, name in enumerate(imgs)
    )
    return (
        f'<div class="carousel" data-idx="0">'
        f'<div class="hero">'
        f'<div class="frames">{frames}</div>'
        f'<button class="nav prev" type="button">‹</button>'
        f'<button class="nav next" type="button">›</button>'
        f'<span class="counter">1 / {len(imgs)}</span>'
        f'</div>'
        f'<div class="thumbs">{thumbs}</div>'
        f'</div>'
    )


def _info(lid, row):
    if not row:
        return (f'<div class="info"><div class="hood">אין פרטים בגיליון</div>'
                f'<h2 class="addr">{_txt(lid)}</h2>'
                f'<a class="btn" target="_blank" '
                f'href="https://www.yad2.co.il/realestate/item/{_txt(lid)}">'
                f'צפייה ב-Yad2</a></div>')

    hood = _txt(row.get("neighborhood")) or "לא צוין"
    addr = " · ".join(p for p in (_txt(row.get("street")),
                                  _txt(row.get("city"))) if p) or _txt(lid)
    rent = _rent(row)
    rent_s = f"₪{rent:,.0f}" if rent > 0 else "—"
    rooms, sqm = _txt(row.get("rooms")), _txt(row.get("sqm"))
    floor, tot = _txt(row.get("floor")), _txt(row.get("total_floors"))
    floor_s = f"{floor}/{tot}" if tot else floor

    chips = "".join(f'<span class="chip">{lbl}</span>'
                    for f, lbl in BOOL_FIELDS if _truthy(row.get(f)))
    meta = "".join(
        f'<div class="meta"><span>{lbl}</span><b>{_txt(row.get(f))}</b></div>'
        for f, lbl in META_FIELDS if _txt(row.get(f))
    )
    decision, notes = _txt(row.get("decision")), _txt(row.get("notes"))
    mark = ""
    if decision or notes:
        mark = (f'<div class="mark">📌 {decision}'
                f'{" — " + notes if notes else ""}</div>')
    desc = _txt(row.get("description"))
    desc_html = f'<p class="desc" dir="auto">{desc}</p>' if desc else ""
    link = _txt(row.get("link")) or \
        f"https://www.yad2.co.il/realestate/item/{_txt(lid)}"

    return f"""<div class="info" dir="rtl">
      <div class="hood">🏘️ שכונה: <b dir="auto">{hood}</b></div>
      <h2 class="addr" dir="auto">{addr}</h2>
      <div class="price">{rent_s}</div>
      <div class="stats"><span>{rooms} חד׳</span><span>{sqm} מ״ר</span>
        <span>קומה {floor_s}</span></div>
      {f'<div class="chips">{chips}</div>' if chips else ''}
      {mark}
      <div class="metas">{meta}</div>
      {desc_html}
      <a class="btn" target="_blank" href="{html.escape(link)}">צפייה ב-Yad2</a>
    </div>"""


PAGE = """<!doctype html><html lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yad2 — גלריית נכסים</title>
<style>
 :root{{color-scheme:light dark}}
 *{{box-sizing:border-box}}
 body{{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;background:#f4f5f7}}
 .topbar{{position:sticky;top:0;z-index:10;display:flex;align-items:center;
   justify-content:center;gap:16px;padding:10px 16px;background:#111;color:#fff}}
 .topbar button{{background:#2a2a2a;color:#fff;border:1px solid #444;
   border-radius:8px;padding:8px 14px;font-size:15px;cursor:pointer}}
 .topbar button:hover{{background:#3a3a3a}}
 #pcount{{font-variant-numeric:tabular-nums;min-width:70px;text-align:center}}
 .stage{{max-width:960px;margin:0 auto;padding:16px}}
 .property{{background:#fff;border-radius:12px;overflow:hidden;
   box-shadow:0 1px 6px rgba(0,0,0,.15)}}
 .hero{{position:relative;background:#000;height:66vh}}
 .frames{{width:100%;height:100%}}
 .frame{{display:none;width:100%;height:100%;object-fit:contain;cursor:zoom-in}}
 .frame.active{{display:block}}
 .nav{{position:absolute;top:50%;transform:translateY(-50%);border:0;
   background:rgba(0,0,0,.5);color:#fff;font-size:30px;width:48px;height:64px;
   cursor:pointer}}
 .prev{{left:0}} .next{{right:0}}
 .counter{{position:absolute;bottom:10px;right:10px;background:rgba(0,0,0,.6);
   color:#fff;font-size:13px;padding:3px 10px;border-radius:10px}}
 .thumbs{{display:flex;gap:6px;overflow-x:auto;padding:8px;background:#181818}}
 .thumb{{height:56px;width:80px;object-fit:cover;border-radius:4px;
   opacity:.55;cursor:pointer;flex:0 0 auto}}
 .thumb.active{{opacity:1;outline:2px solid #4a9eff}}
 .info{{padding:16px 18px;display:flex;flex-direction:column;gap:10px}}
 .hood{{font-size:16px;background:#eef4ff;border:1px solid #cfe0ff;
   border-radius:8px;padding:6px 12px;align-self:flex-start}}
 .hood b{{font-size:18px;margin-inline-start:4px}}
 .addr{{margin:0;font-size:17px;font-weight:600;color:#333}}
 .price{{font-size:24px;font-weight:800;color:#0a7d33}}
 .stats{{display:flex;gap:14px;flex-wrap:wrap;color:#333;font-size:15px}}
 .chips{{display:flex;gap:6px;flex-wrap:wrap}}
 .chip{{background:#eef;border-radius:20px;padding:3px 12px;font-size:13px}}
 .metas{{display:flex;gap:12px;flex-wrap:wrap}}
 .meta{{font-size:13px;color:#555}} .meta b{{color:#111;margin-inline-start:4px}}
 .mark{{background:#fff6d6;border:1px solid #f0d24b;border-radius:8px;
   padding:6px 10px;font-size:14px}}
 .desc{{font-size:14px;color:#444;margin:0;max-height:8em;overflow:auto;
   line-height:1.5}}
 .btn{{align-self:flex-start;background:#111;color:#fff;text-decoration:none;
   padding:8px 14px;border-radius:8px;font-size:14px}}
</style></head><body>
<div class="topbar">
  <button id="pprev" type="button">‹ הקודם</button>
  <span id="pcount">1 / {count}</span>
  <button id="pnext" type="button">הבא ›</button>
</div>
<div class="stage">{properties}</div>
<script>
 var props=Array.prototype.slice.call(document.querySelectorAll('.property'));
 var cur=0, pcount=document.getElementById('pcount');
 function showProp(i){{
   var n=props.length; i=(i%n+n)%n;
   props.forEach(function(p,j){{p.hidden=(j!==i)}});
   cur=i; pcount.textContent=(i+1)+' / '+n; window.scrollTo(0,0);
 }}
 document.getElementById('pprev').onclick=function(){{showProp(cur-1)}};
 document.getElementById('pnext').onclick=function(){{showProp(cur+1)}};
 document.querySelectorAll('.carousel').forEach(function(c){{
   var frames=c.querySelectorAll('.frame'), thumbs=c.querySelectorAll('.thumb'),
       counter=c.querySelector('.counter');
   function show(i){{
     var n=frames.length; i=(i%n+n)%n;
     frames.forEach(function(f,j){{f.classList.toggle('active',j===i)}});
     thumbs.forEach(function(t,j){{t.classList.toggle('active',j===i)}});
     c.dataset.idx=i; counter.textContent=(i+1)+' / '+n;
   }}
   c._step=function(d){{show(+c.dataset.idx+d)}};
   c.querySelector('.prev').onclick=function(){{c._step(-1)}};
   c.querySelector('.next').onclick=function(){{c._step(1)}};
   thumbs.forEach(function(t){{t.onclick=function(){{show(+t.dataset.i)}}}});
 }});
 document.addEventListener('keydown',function(e){{
   var c=props[cur].querySelector('.carousel');
   if(e.key==='ArrowLeft'&&c)c._step(-1);
   else if(e.key==='ArrowRight'&&c)c._step(1);
   else if(e.key==='ArrowUp')showProp(cur-1);
   else if(e.key==='ArrowDown')showProp(cur+1);
 }});
</script></body></html>"""


def main():
    from datetime import datetime
    rows = _load_sheet_rows()
    folders = _property_folders()
    if not folders:
        print(f"No photo folders found under {PHOTOS_DIR}. Nothing to build.")
        return
    # Cheapest-first when we have prices, else by id.
    folders.sort(key=lambda t: (_rent(rows.get(t[0], {})) or 1e12, t[0]))

    sections = []
    for i, (lid, imgs) in enumerate(folders):
        row = rows.get(lid)
        hidden = "" if i == 0 else " hidden"
        sections.append(
            f'<section class="property" data-i="{i}"{hidden}>'
            f'{_carousel(lid, imgs)}{_info(lid, row)}</section>'
        )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(PAGE.format(count=len(folders), properties="".join(sections)))

    matched = sum(1 for lid, _ in folders if lid in rows)
    print(f"✅ Wrote {OUT}")
    print(f"   {len(folders)} properties, {matched} matched to sheet rows.")


if __name__ == "__main__":
    main()
