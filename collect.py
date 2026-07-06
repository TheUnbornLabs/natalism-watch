#!/usr/bin/env python3
"""
Natalism Dashboard collector.

Pulls fresh items about antinatalism / childfree / pro-natalism from:
  - Reddit (free, no key)
  - Google News RSS (free, no key)
  - Academic / philosophy news (free, no key, via Google News query)
  - X/Twitter (optional, needs Bearer token)
  - YouTube (optional, needs API key)

Stores everything in a local SQLite database (data.db), de-duplicated by URL,
then regenerates a self-contained dashboard.html you can open in any browser.

Run it:  python collect.py
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
DB_PATH = os.path.join(HERE, "data.db")
DASHBOARD_PATH = os.path.join(HERE, "dashboard.html")

UA = "Mozilla/5.0 (NatalismDashboard/1.0; personal research aggregator)"

# The Windows console defaults to cp1252, which cannot encode non-Latin text
# (e.g. Japanese). Switch stdout/stderr to UTF-8 so logging never crashes a fetch.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, AttributeError):
        # Last-resort fallback if a stream can't encode or isn't available.
        try:
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get(url, timeout, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_text(s, limit=320):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)          # strip html tags
    s = re.sub(r"&[a-z]+;", " ", s)         # strip simple entities
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def iso(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# database
# --------------------------------------------------------------------------- #
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            url          TEXT PRIMARY KEY,
            topic        TEXT NOT NULL,
            source_type  TEXT NOT NULL,
            source_name  TEXT,
            title        TEXT,
            snippet      TEXT,
            published_at TEXT,
            collected_at TEXT NOT NULL,
            language     TEXT NOT NULL DEFAULT 'en'
        )
        """
    )
    # Migration: add `language` to databases created before multi-language support.
    cols = [r[1] for r in con.execute("PRAGMA table_info(items)").fetchall()]
    if "language" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
    con.commit()
    return con


def save_items(con, items):
    """Insert new items, ignore ones we already have. Returns count of new rows."""
    now = iso(datetime.now(timezone.utc))
    new = 0
    for it in items:
        if not it.get("url"):
            continue
        try:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO items
                  (url, topic, source_type, source_name, title, snippet, published_at, collected_at, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    it["url"],
                    it["topic"],
                    it["source_type"],
                    it.get("source_name", ""),
                    it.get("title", ""),
                    it.get("snippet", ""),
                    it.get("published_at"),
                    now,
                    it.get("language", "en"),
                ),
            )
            new += cur.rowcount
        except sqlite3.Error as e:
            log(f"  ! db error on one item: {e}")
    con.commit()
    return new


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_reddit(topic_key, topic, limit, timeout, lang="en"):
    """Reddit's JSON endpoint is now blocked for generic clients, but the
    public Atom feed (/r/<sub>/new/.rss) still works. We parse that.
    Subreddits are overwhelmingly English, so items are tagged with `lang`
    (default 'en') purely for the dashboard's language filter."""
    out = []
    for sub in topic.get("subreddits", []):
        url = f"https://www.reddit.com/r/{sub}/new/.rss?limit={limit}"
        xml_text = None
        for attempt in range(4):  # Reddit RSS rate-limits hard; back off and retry
            try:
                xml_text = http_get(url, timeout)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    wait = 5 * (attempt + 1)
                    log(f"  . reddit r/{sub} rate-limited, waiting {wait}s")
                    time.sleep(wait)
                    continue
                log(f"  ! reddit r/{sub} failed: {e}")
                break
            except Exception as e:
                log(f"  ! reddit r/{sub} failed: {e}")
                break
        if xml_text is None:
            continue
        try:
            root = ET.fromstring(xml_text)
        except Exception as e:
            log(f"  ! reddit r/{sub} parse failed: {e}")
            continue
        n = 0
        for entry in root.findall(f"{ATOM}entry")[:limit]:
            link_el = entry.find(f"{ATOM}link")
            link = link_el.get("href") if link_el is not None else None
            if not link:
                continue
            pub = entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
            content = entry.findtext(f"{ATOM}content") or ""
            out.append(
                {
                    "url": link,
                    "topic": topic_key,
                    "source_type": "reddit",
                    "source_name": f"r/{sub}",
                    "title": clean_text(entry.findtext(f"{ATOM}title"), 240),
                    "snippet": clean_text(content, 320),
                    "published_at": iso(parsedate_to_datetime(pub)) if _is_rfc(pub) else pub,
                    "language": lang,
                }
            )
            n += 1
        log(f"  reddit r/{sub}: {n} items")
        time.sleep(3)  # avoid 429 rate limiting between subreddits
    return out


def _is_rfc(s):
    """Reddit Atom dates are ISO-8601 already, so usually no conversion needed."""
    return bool(s) and "," in s


def _parse_rss(xml_text, topic_key, source_type, language, limit):
    out = []
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")[:limit]
    for item in items:
        link = item.findtext("link")
        if not link:
            continue
        pub = None
        raw_pub = item.findtext("pubDate")
        if raw_pub:
            try:
                pub = iso(parsedate_to_datetime(raw_pub))
            except Exception:
                pub = None
        # google news embeds the real source in <source>
        src = item.findtext("source") or ""
        out.append(
            {
                "url": link,
                "topic": topic_key,
                "source_type": source_type,
                "source_name": clean_text(src, 80),
                "title": clean_text(item.findtext("title"), 240),
                "snippet": clean_text(item.findtext("description"), 320),
                "published_at": pub,
                "language": language,
            }
        )
    return out


def fetch_news(topic_key, query, locale, source_type, language, limit, timeout):
    if not query:
        return []
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&{locale}"
    try:
        xml_text = http_get(url, timeout)
        out = _parse_rss(xml_text, topic_key, source_type, language, limit)
        log(f"  [{language}] {source_type} '{query[:32]}...': {len(out)} items")
        return out
    except Exception as e:
        log(f"  ! [{language}] {source_type} query failed: {e}")
        return []


def fetch_youtube(topic_key, query, language, api_key, limit, timeout):
    if not query or not api_key:
        return []
    q = urllib.parse.quote(query)
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&order=date&maxResults={min(limit, 50)}"
        f"&relevanceLanguage={language}&q={q}&key={api_key}"
    )
    try:
        data = json.loads(http_get(url, timeout))
    except Exception as e:
        log(f"  ! youtube query failed: {e}")
        return []
    out = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        sn = item.get("snippet", {})
        if not vid:
            continue
        pub = sn.get("publishedAt")
        out.append(
            {
                "url": f"https://www.youtube.com/watch?v={vid}",
                "topic": topic_key,
                "source_type": "youtube",
                "source_name": clean_text(sn.get("channelTitle"), 80),
                "title": clean_text(sn.get("title"), 240),
                "snippet": clean_text(sn.get("description"), 320),
                "published_at": pub,
                "language": language,
            }
        )
    log(f"  [{language}] youtube '{query}': {len(out)} items")
    return out


def fetch_twitter(topic_key, query, language, bearer, limit, timeout):
    if not query or not bearer:
        return []
    # X/Twitter API v2 recent search (requires a project with Bearer token)
    q = urllib.parse.quote(f"{query} -is:retweet lang:{language}")
    url = (
        "https://api.twitter.com/2/tweets/search/recent"
        f"?query={q}&max_results={min(max(limit, 10), 100)}"
        "&tweet.fields=created_at,author_id,text"
    )
    headers = {"Authorization": f"Bearer {bearer}", "User-Agent": UA}
    try:
        data = json.loads(http_get(url, timeout, headers=headers))
    except Exception as e:
        log(f"  ! twitter query failed: {e}")
        return []
    out = []
    for t in data.get("data", []):
        tid = t.get("id")
        if not tid:
            continue
        out.append(
            {
                "url": f"https://x.com/i/web/status/{tid}",
                "topic": topic_key,
                "source_type": "twitter",
                "source_name": "X/Twitter",
                "title": clean_text(t.get("text"), 240),
                "snippet": clean_text(t.get("text"), 320),
                "published_at": t.get("created_at"),
                "language": language,
            }
        )
    log(f"  [{language}] twitter '{query}': {len(out)} items")
    return out


# --------------------------------------------------------------------------- #
# dashboard generation
# --------------------------------------------------------------------------- #
def build_payload(con, config):
    """Read the store and return the JSON payload the dashboard consumes."""
    days = config["settings"].get("history_days_shown", 30)
    rows = con.execute(
        """
        SELECT url, topic, source_type, source_name, title, snippet, published_at, collected_at, language
        FROM items
        ORDER BY COALESCE(published_at, collected_at) DESC
        """
    ).fetchall()

    items = [
        {
            "url": r[0],
            "topic": r[1],
            "source_type": r[2],
            "source_name": r[3],
            "title": r[4],
            "snippet": r[5],
            "published_at": r[6],
            "collected_at": r[7],
            "language": r[8] or "en",
        }
        for r in rows
    ]

    topics_meta = {
        k: {"label": v["label"], "color": v["color"]}
        for k, v in config["topics"].items()
    }

    # Only advertise languages that actually have items in the store.
    present = {it["language"] for it in items}
    langs_meta = {
        code: {"label": lc.get("label", code)}
        for code, lc in config.get("languages", {}).items()
        if code in present
    }

    return {
        "generated_at": iso(datetime.now(timezone.utc)),
        "topics": topics_meta,
        "languages": langs_meta,
        "items": items,
        "total": len(items),
        "history_days": days,
    }


def build_dashboard(con, config):
    payload = build_payload(con, config)
    html = DASHBOARD_TEMPLATE.replace(
        "/*__DATA__*/", json.dumps(payload, ensure_ascii=False)
    )
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"dashboard.html written ({payload['total']} items in store)")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def enabled_languages(config):
    """List of (code, lang_config) for languages turned on in config."""
    return [(code, lc) for code, lc in config.get("languages", {}).items() if lc.get("enabled")]


def run_collection(con, config):
    """Fetch every enabled source, for every topic, in every enabled language.
    Returns the number of new items. Reusable by both CLI and the server."""
    enabled = config["sources_enabled"]
    keys = config.get("api_keys", {})
    s = config["settings"]
    limit = s.get("max_items_per_source", 40)
    timeout = s.get("request_timeout_seconds", 25)
    reddit_lang = s.get("reddit_language", "en")
    langs = enabled_languages(config)

    total_new = 0
    for topic_key, topic in config["topics"].items():
        log(f"== topic: {topic['label']} ==")
        collected = []
        topic_queries = topic.get("queries", {})

        # Reddit is language-agnostic (mostly English) — fetch once per topic.
        if enabled.get("reddit"):
            collected += fetch_reddit(topic_key, topic, limit, timeout, lang=reddit_lang)

        # Everything else runs once per enabled language with localized terms.
        for code, lc in langs:
            q = topic_queries.get(code)
            if not q:
                continue  # no translated query for this topic+language
            locale = lc.get("news_locale", "hl=en-US&gl=US&ceid=US:en")
            if enabled.get("news"):
                collected += fetch_news(topic_key, q.get("news"), locale, "news", code, limit, timeout)
            if enabled.get("academic"):
                collected += fetch_news(topic_key, q.get("academic"), locale, "academic", code, limit, timeout)
            if enabled.get("twitter"):
                collected += fetch_twitter(topic_key, q.get("social"), code, keys.get("twitter_bearer_token", ""), limit, timeout)
            if enabled.get("youtube"):
                collected += fetch_youtube(topic_key, q.get("youtube"), code, keys.get("youtube_api_key", ""), limit, timeout)

        new = save_items(con, collected)
        total_new += new
        log(f"  -> {new} new items saved for {topic['label']}")
        time.sleep(1)  # be polite to the free endpoints
    return total_new


def main():
    config = load_config()
    con = init_db()
    total_new = run_collection(con, config)
    build_dashboard(con, config)
    log(f"DONE. {total_new} new items this run. Open dashboard.html in your browser.")
    con.close()


# The dashboard HTML lives in dashboard_template.py to keep this file readable.
from dashboard_template import DASHBOARD_TEMPLATE  # noqa: E402

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
