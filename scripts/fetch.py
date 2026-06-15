#!/usr/bin/env python3
import json, os, sys, re, time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ACCOUNTS = ["pokecachan", "Zabi_pokeka", "gamegetnavi"]
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://lightbrd.com",
    "https://nitter.space",
]
KEYWORDS = ["応募","抽選","プレゼント","キャンペーン","当選","締切","販売","予約","限定","受付","エントリー","BOX","パック"]
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "tweets.json")
USER_AGENT = "Mozilla/5.0 (compatible; PokekaTracker/1.0)"
TIMEOUT = 15

def is_relevant(text):
    return any(k in text for k in KEYWORDS)

def fetch_rss(instance, handle):
    url = f"{instance}/{handle}/rss"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as res:
            if res.status != 200:
                return None
            return res.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

def parse_rss(xml_text, handle):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        clean_title = re.sub(r"<[^>]+>", "", title)
        clean_desc = re.sub(r"<[^>]+>", "", desc)
        combined = clean_title + " " + clean_desc
        x_link = re.sub(r"https?://[^/]+/", "https://x.com/", link)
        items.append({
            "id": link or f"{handle}-{pub}",
            "account": handle,
            "text": clean_title[:200],
            "link": x_link,
            "pubDate": pub,
            "relevant": is_relevant(combined),
        })
    return items

def fetch_account(handle):
    for instance in NITTER_INSTANCES:
        xml = fetch_rss(instance, handle)
        if xml and "<item>" in xml:
            items = parse_rss(xml, handle)
            if items:
                return items, f"OK ({instance})"
        time.sleep(1)
    return [], "FAILED (全インスタンス取得失敗)"

def load_existing():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"updated": None, "tweets": [], "log": []}

def main():
    existing = load_existing()
    existing_tweets = {t["id"]: t for t in existing.get("tweets", [])}
    all_new = []
    log = []
    any_success = False
    for handle in ACCOUNTS:
        items, status = fetch_account(handle)
        log.append(f"{handle}: {status} - {len(items)}件")
        if items:
            any_success = True
            all_new.extend(items)
        print(f"[{handle}] {status} - {len(items)}件", file=sys.stderr)
    if not any_success:
        existing["log"] = log
        existing["lastAttempt"] = datetime.now(timezone.utc).isoformat()
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return
    for t in all_new:
        existing_tweets[t["id"]] = t
    merged = list(existing_tweets.values())
    def sort_key(t):
        try:
            return datetime.strptime(t["pubDate"], "%a, %d %b %Y %H:%M:%S %Z")
        except (ValueError, KeyError):
            return datetime.min
    merged.sort(key=sort_key, reverse=True)
    merged = merged[:400]
    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "lastAttempt": datetime.now(timezone.utc).isoformat(),
        "tweets": merged,
        "log": log,
    }
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"保存完了: 合計{len(merged)}件", file=sys.stderr)

if __name__ == "__main__":
    main()
