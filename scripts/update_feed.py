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


def infer_category(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    rules = [
        ("Verkehr", ["verkehr", "unfall", "sperrung", "stau", "brücke", "bruecke", "a100", "fahrzeug", "auto", "fußgänger", "fussgänger", "radfahrer", "bahn", "s-bahn", "u-bahn", "tram", "bus"]),
        ("Fahndung", ["fahndung", "gesucht", "vermisst", "zeugen", "tatverdächt", "tatverdaecht", "hinweis"]),
        ("Ermittlung", ["ermittlung", "ermitteln", "brand", "diebstahl", "raub", "angriff", "drogen", "betrug", "beschädigung", "sachbeschädigung", "verletz", "festnahme"]),
        ("Einsatz", ["einsatz", "polizei", "streife", "beamte", "sichert", "kontrolle", "festnahme"]),
    ]
    for category, keywords in rules:
        if any(k in text for k in keywords):
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
