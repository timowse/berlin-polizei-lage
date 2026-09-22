#!/usr/bin/env python3
from __future__ import annotations

import email.utils
import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "feed.json"
RSS_URL = "https://www.berlin.de/polizei/polizeimeldungen/index.php/rss"
UA = "Mozilla/5.0 (X11; Linux x86_64) HermesAgent/1.0"
LIMIT = 18


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def meta_description(page_html: str) -> str:
    patterns = [
        r'<meta\s+name="description"\s+content="([^"]+)"',
        r"<meta\s+name='description'\s+content='([^']+)'",
        r'<meta\s+property="og:description"\s+content="([^"]+)"',
        r"<meta\s+property='og:description'\s+content='([^']+)'",
    ]
    for pattern in patterns:
        m = re.search(pattern, page_html, re.I)
        if m:
            return clean_text(m.group(1))

    # Fallback: first meaningful paragraph-like content.
    for p in re.findall(r"<p[^>]*>(.*?)</p>", page_html, re.S | re.I):
        text = clean_text(p)
        low = text.lower()
        if len(text) > 60 and not low.startswith((
            "polizei berlin",
            "barrierefreiheit",
            "erklärung zur barrierefreiheit",
            "kontakt",
            "suche",
            "hauptnavigation",
        )):
            return text
    return ""


# Keywords greifen nur am Wortanfang. Deutsche Komposita matchen damit weiter
# ("Verkehrsunfall" -> verkehr), Zufallstreffer im Wortinneren nicht mehr
# ("Restaurant" enthielt zuvor "stau" und landete unter Verkehr).
# Spiegelt CATEGORY_RULES in index.html - beide Listen synchron halten.
CATEGORY_RULES = [
    # Starke Verkehrssignale: das Ereignis selbst ist ein Verkehrsvorgang.
    ("Verkehr", ["verkehr", "unfall", "sperrung", "stau", "brücke", "bruecke", "a100", "autobahn", "fahrzeug", "pkw", "lkw", "fußgänger", "fussgänger", "radfahrer", "radfahrende", "motorrad", "roller", "kollision", "falschfahrer"]),
    ("Fahndung", ["fahndung", "gesucht", "vermisst", "zeug", "zeuginnen", "öffentlichkeitsfahndung"]),
    ("Ermittlung", ["ermittl", "brandstiftung", "brand", "diebstahl", "einbruch", "raub", "überfall", "angriff", "drogen", "betrug", "sachbeschädig", "beschädig", "verletz", "festnahme", "festgenommen", "messer", "schuss", "schüsse", "schießerei", "tötung", "tatverdächt", "tatverdaecht"]),
    ("Einsatz", ["einsatz", "streife", "alarmiert", "razzia", "durchsuchung", "kontroll", "demonstration", "versammlung", "absperrung", "evakuier"]),
    # Schwache Verkehrssignale: blosse Ortsangaben. Erst greifen, wenn oben
    # nichts passte - sonst wuerde "Bedrohung am U-Bahnhof" zur Verkehrsmeldung.
    ("Verkehr", ["bahnhof", "s-bahn", "u-bahn", "straßenbahn", "strassenbahn", "tram", "bus"]),
]

# "Brandenburg" darf nicht als Brand durchgehen.
CATEGORY_BLOCKLIST = re.compile(r"(?<![0-9A-Za-zÀ-ÖØ-öø-ÿ])brandenburg", re.I)

WORD_START = r"(?<![0-9A-Za-zÀ-ÖØ-öø-ÿ])"
_MATCHERS = [
    (category, [re.compile(WORD_START + re.escape(k), re.I) for k in keywords])
    for category, keywords in CATEGORY_RULES
]


def infer_category(title: str, summary: str) -> str:
    text = CATEGORY_BLOCKLIST.sub(" ", f"{title} {summary}")
    for category, matchers in _MATCHERS:
        if any(m.search(text) for m in matchers):
            return category
    return "Sonstiges"


def parse_pubdate(pubdate: str) -> datetime:
    dt = email.utils.parsedate_to_datetime(pubdate)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def pretty_time(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def main() -> int:
    rss = fetch(RSS_URL)
    root = ET.fromstring(rss)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("RSS channel not found")

    items = []
    fetched_at = datetime.now().astimezone()
    for item in channel.findall("item")[:LIMIT]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pubdate = parse_pubdate(item.findtext("pubDate") or fetched_at.isoformat())

        summary = ""
        try:
            page = fetch(link)
            summary = meta_description(page)
        except (urllib.error.URLError, TimeoutError, RuntimeError):
            summary = ""

        if not summary:
            summary = title

        items.append({
            "title": title,
            "link": link,
            "publishedAt": pubdate.isoformat(),
            "publishedLabel": pretty_time(pubdate),
            "summary": summary,
            "category": infer_category(title, summary),
        })

    if items:
        latest = items[0]
    else:
        latest = {"title": "Keine Meldungen", "publishedAt": fetched_at.isoformat(), "publishedLabel": pretty_time(fetched_at)}

    data = {
        "source": {
            "name": "Polizei Berlin",
            "url": RSS_URL,
            "count": len(items),
            "checkedAt": fetched_at.isoformat(),
            "checkedTime": fetched_at.strftime("%H:%M Uhr"),
            "statusLabel": "Aktuell",
            "latestTitle": latest["title"],
            "latestPublishedAt": latest["publishedAt"],
        },
        "items": items,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {DATA_FILE} with {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
