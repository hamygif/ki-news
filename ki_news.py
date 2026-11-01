#!/usr/bin/env python3
"""KI News – holt KI-Artikel der letzten 24 Stunden aus RSS/Atom-Feeds
und erzeugt daraus eine Web-App-Seite (site/index.html).

Nur Python-Standardbibliothek, keine Installation nötig.
Aufruf:  python3 ki_news.py
"""

import concurrent.futures
import html
import os
import re
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

try:
    from zoneinfo import ZoneInfo
    BERLIN = ZoneInfo("Europe/Berlin")
except Exception:  # Fallback, falls keine Zeitzonendaten vorhanden sind
    BERLIN = timezone(timedelta(hours=1))

# Getestete Feeds (Stand Nov. 2026). Feeds, die beim Abruf scheitern,
# werden automatisch übersprungen.
FEEDS = [
    ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Wired", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("Ars Technica", "https://arstechnica.com/ai/feed/"),
    ("The Decoder", "https://the-decoder.de/feed/"),
]

HOURS = 24
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
USER_AGENT = "Mozilla/5.0 (compatible; KI-News/1.0; +https://github.com)"

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember"]


def ssl_context():
    """Zertifikatsprüfung bleibt immer an. Auf macOS fehlen dem python.org-
    Python manchmal die Zertifikate – dann nehmen wir die des Systems."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0 and os.path.exists("/etc/ssl/cert.pem"):
        ctx.load_verify_locations("/etc/ssl/cert.pem")
    return ctx


CTX = ssl_context()


def fetch(url, tries=2):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                return r.read()
        except Exception as e:
            last = e
    raise last


def parse_date(text):
    if not text:
        return None
    text = text.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(text)  # RSS: "Sun, 01 Nov 2026 10:00:00 +0000"
    except Exception:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))  # Atom: ISO 8601
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def clean(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_feed(source, data):
    root = ET.fromstring(data)
    items = []
    for it in root.iter("item"):  # RSS 2.0
        items.append({
            "title": clean(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "date": parse_date(it.findtext("pubDate") or it.findtext(DC + "date")),
        })
    for e in root.iter(ATOM + "entry"):  # Atom
        link = ""
        for l in e.findall(ATOM + "link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        items.append({
            "title": clean(e.findtext(ATOM + "title")),
            "link": link.strip(),
            "date": parse_date(e.findtext(ATOM + "published") or e.findtext(ATOM + "updated")),
        })
    for i in items:
        i["source"] = source
    return [i for i in items if i["title"] and i["link"].startswith("http") and i["date"]]


def load(feed):
    source, url = feed
    return parse_feed(source, fetch(url))


def collect():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=HOURS)
    articles, ok, failed = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(load, f): f for f in FEEDS}
        for fut in concurrent.futures.as_completed(futures):
            source, url = futures[fut]
            try:
                items = fut.result()
                ok.append(source)
                articles += [a for a in items if cutoff <= a["date"] <= now + timedelta(minutes=10)]
            except Exception as e:
                failed.append(source)
                print(f"  ✗ {source}: {e}", file=sys.stderr)
    seen, unique = set(), []
    for a in sorted(articles, key=lambda a: a["date"], reverse=True):
        key = a["link"].split("?")[0].rstrip("/")
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique, sorted(ok), sorted(failed), now


def deutsches_datum(dt):
    return f"{WOCHENTAGE[dt.weekday()]}, {dt.day}. {MONATE[dt.month - 1]} {dt.year}, {dt:%H:%M} Uhr"


def zeit_label(dt, today):
    local = dt.astimezone(BERLIN)
    if local.date() == today:
        tag = "Heute"
    elif local.date() == today - timedelta(days=1):
        tag = "Gestern"
    else:
        tag = f"{local.day}.{local.month}."
    return f"{tag}, {local:%H:%M}"


def render(articles, ok, now):
    e = html.escape
    local_now = now.astimezone(BERLIN)
    today = local_now.date()
    if articles:
        rows = "\n".join(
            f'''      <li><a class="card" href="{e(a["link"])}" target="_blank" rel="noopener">
        <div class="meta"><span class="src">{e(a["source"])}</span><time datetime="{a["date"].isoformat()}">{zeit_label(a["date"], today)}</time></div>
        <h2>{e(a["title"])}</h2>
      </a></li>'''
            for a in articles)
    else:
        rows = '      <li class="empty">In den letzten 24 Stunden gab es keine neuen Artikel.</li>'

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>KI News</title>
<meta name="description" content="Die KI-Nachrichten der letzten 24 Stunden">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="KI News">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0b0d12">
<meta name="format-detection" content="telephone=no">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="icon" type="image/png" href="favicon.png">
<style>
  :root {{
    --bg: #0b0d12; --card: #161a23; --card-active: #1f2533;
    --text: #e8eaf0; --muted: #8b93a7; --accent: #7c9cff; --line: #232938;
  }}
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html {{ background: var(--bg); color-scheme: dark; }}
  body {{
    margin: 0; color: var(--text);
    font: 17px/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
    padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
    -webkit-text-size-adjust: 100%;
  }}
  header {{
    position: sticky; top: 0; z-index: 1;
    padding: calc(env(safe-area-inset-top) + 14px) 18px 12px;
    margin-top: calc(-1 * env(safe-area-inset-top));
    background: rgba(11, 13, 18, .85);
    -webkit-backdrop-filter: saturate(180%) blur(18px); backdrop-filter: saturate(180%) blur(18px);
    border-bottom: 1px solid var(--line);
  }}
  h1 {{ margin: 0; font-size: 30px; font-weight: 800; letter-spacing: -.02em; }}
  h1 span {{ color: var(--accent); }}
  .updated {{ margin-top: 2px; font-size: 13px; color: var(--muted); }}
  main {{ max-width: 720px; margin: 0 auto; padding: 12px 12px 28px; }}
  ul {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
  .card {{
    display: block; padding: 14px 16px; border-radius: 16px;
    background: var(--card); color: inherit; text-decoration: none;
    transition: background .15s, transform .15s;
  }}
  .card:active {{ background: var(--card-active); transform: scale(.985); }}
  .meta {{ display: flex; justify-content: space-between; gap: 10px; font-size: 13px; color: var(--muted); }}
  .src {{ color: var(--accent); font-weight: 600; }}
  h2 {{ margin: 6px 0 0; font-size: 17px; font-weight: 600; line-height: 1.35; }}
  .empty {{ padding: 40px 16px; text-align: center; color: var(--muted); }}
  footer {{ padding: 8px 18px 24px; text-align: center; font-size: 12px; color: var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>KI <span>News</span></h1>
  <div class="updated">Aktualisiert: {deutsches_datum(local_now)} · {len(articles)} Artikel</div>
</header>
<main>
  <ul>
{rows}
  </ul>
</main>
<footer>Quellen: {e(", ".join(ok))}<br>Artikel der letzten {HOURS} Stunden, neueste zuerst.</footer>
</body>
</html>
'''


MANIFEST = '''{
  "name": "KI News",
  "short_name": "KI News",
  "description": "Die KI-Nachrichten der letzten 24 Stunden",
  "lang": "de",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#0b0d12",
  "theme_color": "#0b0d12",
  "icons": [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
'''


def main():
    print("Hole KI-News …")
    articles, ok, failed, now = collect()
    if not ok:
        sys.exit("Kein einziger Feed erreichbar – Seite wird nicht überschrieben.")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(articles, ok, now))
    with open(os.path.join(OUT_DIR, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        f.write(MANIFEST)
    print(f"  ✓ {len(ok)} Feeds ok: {', '.join(ok)}")
    if failed:
        print(f"  ✗ {len(failed)} Feeds übersprungen: {', '.join(failed)}")
    print(f"  → {len(articles)} Artikel in site/index.html geschrieben")


if __name__ == "__main__":
    main()
