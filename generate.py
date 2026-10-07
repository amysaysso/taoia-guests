#!/usr/bin/env python3
"""
The Art of Imperfect Adulting - Guest Directory generator.

Reads the guest Google Sheet (published as CSV) and writes a static,
crawler-readable page into ./public:
  - index.html   every guest card written directly into the HTML,
                 plus schema.org structured data
  - sitemap.xml, robots.txt, CNAME (if CUSTOM_DOMAIN is set)

Columns used on the page:   Guest Name, Episode Title, Link to Episode Article,
                            Guest Website Addy (only when Backlink Y/N is "Y"),
                            YouTube Link
Columns used but NEVER shown or written into the page:
                            Release Date, Episode # (sorting only),
                            Backlink Y/N (decides whether the website link shows)
Column ignored entirely:    Category

Settings (environment variables):
  SHEET_CSV_URL     required  published CSV link (or a local .csv path for testing)
  SITE_URL          optional  e.g. https://guests.amysaysso.com
  CUSTOM_DOMAIN     optional  e.g. guests.amysaysso.com
  OLD_ARTICLE_BASE  optional  e.g. https://www.imperfectadulting.com
  NEW_ARTICLE_BASE  optional  e.g. https://amysaysso.com/imperfectadulting
                    When both are set, article links starting with the old
                    address are rewritten to the new one. Use this after the
                    site move so you never have to edit the Sheet.

Uses only the Python standard library.
"""

import csv
import html
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "").strip()
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
CUSTOM_DOMAIN = os.environ.get("CUSTOM_DOMAIN", "").strip()
OLD_ARTICLE_BASE = os.environ.get("OLD_ARTICLE_BASE", "").strip().rstrip("/")
NEW_ARTICLE_BASE = os.environ.get("NEW_ARTICLE_BASE", "").strip().rstrip("/")

SHOW_NAME = "The Art of Imperfect Adulting"
SHOW_URL = "https://www.youtube.com/@imperfectadulting"
SITE_TITLE = f"{SHOW_NAME} Guest Directory"
SITE_DESCRIPTION = (
    f"Every guest interviewed on {SHOW_NAME}, the podcast and video show "
    "featuring women navigating life's challenging chapters. Read each "
    "conversation or watch it on YouTube."
)
OUT_DIR = "public"
EMPTY_VALUES = {"", "n/a", "na", "none", "-", "null", "tbd"}


# ---------- reading the sheet ----------

def load_rows(source):
    if not source:
        sys.exit("SHEET_CSV_URL is not set.")
    if re.match(r"^https?://", source):
        req = urllib.request.Request(source, headers={"User-Agent": "taoia-guest-directory-builder"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8-sig")
    else:
        with open(source, encoding="utf-8-sig") as f:
            text = f.read()
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(io.StringIO(text))]


def is_blank(value):
    return (value or "").strip().lower() in EMPTY_VALUES


def parse_date(value):
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime((value or "").strip(), fmt)
        except ValueError:
            continue
    return datetime.min


def episode_number(value):
    m = re.search(r"\d+(\.\d+)?", value or "")
    return float(m.group()) if m else -1.0


# ---------- cleaning values ----------

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "guest"


def to_url(value):
    v = (value or "").strip()
    if is_blank(v):
        return None
    if re.match(r"^https?://", v, re.I):
        return v
    if re.match(r"^(www\.)?([\w-]+\.)+[a-z]{2,}(/.*)?$", v, re.I):
        return "https://" + v
    return None


def rewrite_article(url):
    """Swap the old site address for the new one, with or without www and http/https."""
    if not (url and OLD_ARTICLE_BASE and NEW_ARTICLE_BASE):
        return url
    old_host = re.sub(r"^https?://(www\.)?", "", OLD_ARTICLE_BASE, flags=re.I)
    m = re.match(r"^https?://(www\.)?" + re.escape(old_host) + r"(?=/|$|\?|#)", url, re.I)
    return NEW_ARTICLE_BASE + url[m.end():] if m else url


def youtube_id(url):
    if not url:
        return None
    p = urllib.parse.urlparse(url)
    host = p.netloc.lower().replace("www.", "").replace("m.", "")
    if host == "youtu.be":
        vid = p.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com"):
        q = urllib.parse.parse_qs(p.query)
        if "v" in q:
            vid = q["v"][0]
        else:
            parts = [x for x in p.path.split("/") if x]
            vid = parts[1] if len(parts) > 1 and parts[0] in {"shorts", "live", "embed", "v"} else None
    else:
        vid = None
    return vid if vid and re.match(r"^[\w-]{6,20}$", vid) else None


def is_yes(value):
    return (value or "").strip().lower() in {"y", "yes", "true", "x"}


# ---------- building the page ----------

def build_guests(rows):
    usable = [r for r in rows if not is_blank(r.get("Guest Name")) and not is_blank(r.get("Episode Title"))]
    # Newest first: by episode number, then by release date. Neither is shown.
    usable.sort(key=lambda r: (episode_number(r.get("Episode #")), parse_date(r.get("Release Date"))), reverse=True)
    guests, used = [], set()
    for r in usable:
        slug = slugify(r["Guest Name"])
        base, n = slug, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        yt = to_url(r.get("YouTube Link"))
        guests.append({
            "slug": slug,
            "name": r["Guest Name"],
            "title": r["Episode Title"],
            "article": rewrite_article(to_url(r.get("Link to Episode Article"))),
            "website": to_url(r.get("Guest Website Addy")) if is_yes(r.get("Backlink Y/N")) else None,
            "youtube": yt,
            "yt_id": youtube_id(yt),
        })
    return guests


def card_html(g):
    e = html.escape
    title_link = g["article"] or g["youtube"]
    title = (f'<a href="{e(title_link, quote=True)}">{e(g["title"])}</a>' if title_link else e(g["title"]))
    thumb = ""
    if g["yt_id"]:
        thumb = (f'<a class="thumb" href="{e(g["youtube"], quote=True)}" rel="noopener" target="_blank" '
                 f'aria-label="Watch {e(g["name"], quote=True)} on YouTube">'
                 f'<img src="https://i.ytimg.com/vi/{g["yt_id"]}/hqdefault.jpg" alt="" loading="lazy" '
                 f'width="480" height="360"></a>')
    links = []
    if g["article"]:
        links.append(f'<li><a href="{e(g["article"], quote=True)}">Read the story</a></li>')
    if g["youtube"]:
        links.append(f'<li><a href="{e(g["youtube"], quote=True)}" rel="noopener" target="_blank">Watch on YouTube</a></li>')
    if g["website"]:
        links.append(f'<li><a href="{e(g["website"], quote=True)}" rel="noopener" target="_blank">'
                     f'Visit {e(g["name"].split(" ")[0])}\'s website</a></li>')
    search = f'{g["name"]} {g["title"]}'.lower()
    return f"""
      <article class="card" id="{g['slug']}" data-search="{e(search, quote=True)}">
        {thumb}
        <div class="body">
          <h2 class="guest"><a href="#{g['slug']}">{e(g['name'])}</a></h2>
          <p class="title">{title}</p>
          {f'<ul class="links">{"".join(links)}</ul>' if links else ''}
        </div>
      </article>"""


def structured_data(guests):
    series = {"@type": "PodcastSeries", "name": SHOW_NAME, "url": SHOW_URL}
    items = []
    for i, g in enumerate(guests, start=1):
        guest = {"@type": "Person", "name": g["name"]}
        if g["website"]:
            guest["url"] = g["website"]
        ep = {
            "@type": "PodcastEpisode",
            "name": g["title"],
            "partOfSeries": series,
            "actor": guest,
        }
        if g["article"]:
            ep["url"] = g["article"]
        if SITE_URL:
            ep["@id"] = f"{SITE_URL}/#{g['slug']}"
        if g["yt_id"]:
            ep["video"] = {
                "@type": "VideoObject",
                "name": g["title"],
                "description": f'{g["name"]} on {SHOW_NAME}: {g["title"]}',
                "thumbnailUrl": f'https://i.ytimg.com/vi/{g["yt_id"]}/hqdefault.jpg',
                "embedUrl": f'https://www.youtube.com/embed/{g["yt_id"]}',
                "url": g["youtube"],
            }
        items.append({"@type": "ListItem", "position": i, "item": ep})
    data = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": SITE_TITLE,
        "description": SITE_DESCRIPTION,
        "about": series,
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
    }
    if SITE_URL:
        data["url"] = SITE_URL + "/"
    text = json.dumps(data, ensure_ascii=False, indent=1)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_page(guests):
    e = html.escape
    updated = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    canonical = f'<link rel="canonical" href="{e(SITE_URL)}/">' if SITE_URL else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(SITE_TITLE)}</title>
<meta name="description" content="{e(SITE_DESCRIPTION, quote=True)}">
{canonical}
<meta property="og:title" content="{e(SITE_TITLE, quote=True)}">
<meta property="og:description" content="{e(SITE_DESCRIPTION, quote=True)}">
<meta property="og:type" content="website">
<script type="application/ld+json">
{structured_data(guests)}
</script>
<style>
  :root {{
    --bg: #faf8f5; --surface: #ffffff; --text: #1f1d1a; --muted: #6b655d;
    --line: #e7e2da; --accent: #b4304a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #171513; --surface: #211f1c; --text: #f2eee8; --muted: #a8a196;
      --line: #36322d; --accent: #f08aa0; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
    font: 16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 1120px; margin: 0 auto; padding: 40px 16px 64px; }}
  header h1 {{ font-size: clamp(1.8rem, 4vw, 2.6rem); line-height: 1.15; margin: 0 0 8px; letter-spacing: -0.01em; }}
  header p {{ color: var(--muted); max-width: 62ch; margin: 0 0 24px; }}
  .search {{ width: 100%; max-width: 420px; font: inherit; padding: 10px 12px; border: 1px solid var(--line);
    border-radius: 8px; background: var(--surface); color: var(--text); }}
  .count {{ color: var(--muted); font-size: 0.9rem; margin: 10px 0 20px; }}
  .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }}
  .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    overflow: hidden; display: flex; flex-direction: column; scroll-margin-top: 16px; }}
  .card:target {{ outline: 2px solid var(--accent); }}
  .card[hidden] {{ display: none; }}
  .thumb img {{ display: block; width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: cover; }}
  .body {{ padding: 16px 18px 18px; display: flex; flex-direction: column; gap: 6px; flex: 1; }}
  .guest {{ font-size: 1.1rem; margin: 0; line-height: 1.3; }}
  .guest a {{ color: inherit; text-decoration: none; }}
  .title {{ margin: 0; color: var(--muted); font-size: 0.95rem; }}
  .title a {{ color: inherit; text-decoration: none; }}
  .title a:hover, .guest a:hover {{ color: var(--accent); }}
  .links {{ list-style: none; padding: 8px 0 0; margin: auto 0 0; display: flex; flex-wrap: wrap; gap: 6px 14px; }}
  .links a {{ color: var(--accent); font-size: 0.9rem; font-weight: 600; text-decoration: none; }}
  .links a:hover {{ text-decoration: underline; }}
  footer {{ margin-top: 48px; color: var(--muted); font-size: 0.85rem; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{e(SITE_TITLE)}</h1>
    <p>{e(SITE_DESCRIPTION)}</p>
  </header>
  <input type="search" class="search" id="q" placeholder="Search guests and episodes" aria-label="Search guests and episodes">
  <p class="count" id="count">{len(guests)} guests</p>
  <main class="grid">{''.join(card_html(g) for g in guests)}
  </main>
  <footer>Updated {updated}.</footer>
</div>
<script>
(function () {{
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var q = document.getElementById('q'), count = document.getElementById('count');
  q.addEventListener('input', function () {{
    var s = q.value.trim().toLowerCase(), n = 0;
    cards.forEach(function (c) {{ var ok = !s || c.dataset.search.indexOf(s) > -1; c.hidden = !ok; if (ok) n++; }});
    count.textContent = n + (n === 1 ? ' guest' : ' guests');
  }});
}})();
</script>
</body>
</html>
"""


def main():
    rows = load_rows(SHEET_CSV_URL)
    guests = build_guests(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_page(guests))
    if SITE_URL:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with open(os.path.join(OUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                    f"  <url><loc>{html.escape(SITE_URL)}/</loc><lastmod>{today}</lastmod></url>\n"
                    "</urlset>\n")
    with open(os.path.join(OUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else ""))
    if CUSTOM_DOMAIN:
        with open(os.path.join(OUT_DIR, "CNAME"), "w", encoding="utf-8") as f:
            f.write(CUSTOM_DOMAIN + "\n")
    print(f"Built guest directory with {len(guests)} guests from {len(rows)} sheet rows.")


if __name__ == "__main__":
    main()
