import json
import os
import re
import time
from datetime import datetime
import hashlib
from approvals import add_and_send

import feedparser
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()  # reads GEMINI_API_KEY from your .env file

MODELS = ["gemini-3.6-flash", "gemini-3.5-flash"]  # second one is a backup
CACHE_FILE = "drafts_cache.json"
SECONDS_BETWEEN_CALLS = 13  # keeps us under 5 requests per minute
last_call_time = 0.0

FEEDS = [
    "https://www.kdnuggets.com/feed",
    "https://towardsdatascience.com/feed",
    "https://huggingface.co/blog/feed.xml",
]

KEYWORDS = [
    "data science", "machine learning", "python", "sql", "llm", "ai",
    "analytics", "pandas", "visualization", "statistics", "dashboard",
    "agent", "agents", "rag", "kaggle", "deep learning", "forecasting",
]

WEEK = 7 * 24 * 3600  # one week, in seconds


# ---------- Part 1: collect articles ----------

def fetch_rss():
    items = []
    cutoff = time.time() - WEEK
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            if getattr(entry, "published_parsed", None):
                ts = time.mktime(entry.published_parsed)
            else:
                ts = time.time()
            if ts >= cutoff:
                items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", "")[:600],
                    "ts": ts,
                    "points": 0,
                })
    return items


def fetch_hn():
    items = []
    cutoff = int(time.time() - WEEK)
    for query in ["data science", "machine learning", "python data"]:
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff},points>30",
                },
                timeout=15,
            ).json()
        except Exception as error:
            print("Hacker News failed:", error)
            continue
        for hit in r.get("hits", []):
            if hit.get("url"):
                items.append({
                    "title": hit["title"],
                    "link": hit["url"],
                    "summary": "",
                    "ts": hit["created_at_i"],
                    "points": hit["points"],
                })
    return items


# ---------- Part 2: rank them ----------

def score(item):
    text = (item["title"] + " " + item["summary"]).lower()
    padded = " " + re.sub(r"[^a-z0-9 ]", " ", text) + " "
    keyword_hits = sum(1 for k in KEYWORDS if " " + k + " " in padded)
    freshness = 1 - (time.time() - item["ts"]) / WEEK
    popularity = min(item["points"], 300) / 100
    return keyword_hits * 2 + popularity + freshness


def top_items(n=5):
    ranked = sorted(fetch_rss() + fetch_hn(), key=score, reverse=True)
    seen = set()
    result = []
    for item in ranked:
        key = item["title"].lower()[:50]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result[:n]


# ---------- Part 3: write the drafts ----------

VOICE = """You write LinkedIn posts for a BSc Data Science and Analytics student who
learns in public. Write in first person, like a real student talking to peers.

Style:
- Curious, direct, plain English. No hype, no buzzwords, no corporate tone.
- 100 to 150 words. At most one emoji, and only if it fits naturally.
- Do NOT start any sentence with 'As a student' or 'As a data science student'.

Structure:
1. Hook: one specific, concrete line (a number, a surprising result, or a clear question).
2. What the article found, in 2 to 3 short sentences, using the most specific detail available.
3. One line starting with 'Why it matters:' giving a practical reason for data science students.
4. One line starting with 'What I want to explore next:' written as curiosity or a learning goal.
5. One closing question that invites real answers.
6. Three relevant hashtags on the last line.

Rules: use only facts that appear in the title and summary provided. Never invent
statistics, quotes or claims. NEVER say or imply that the student built, tested, ran or
tried anything themselves. Do not mention being an AI. Do not include the link."""

def wait_for_slot():
    """Make sure at least 13 seconds pass between two API calls."""
    global last_call_time
    gap = time.time() - last_call_time
    if gap < SECONDS_BETWEEN_CALLS:
        time.sleep(SECONDS_BETWEEN_CALLS - gap)
    last_call_time = time.time()


exhausted_models = set()  # models that hit their daily limit


def draft(item):
    clean_summary = re.sub(r"<[^>]+>", " ", item["summary"])  # remove HTML tags
    prompt = (
        f"Title: {item['title']}\n"
        f"Link: {item['link']}\n"
        f"Summary: {clean_summary}"
    )
    for attempt in range(8):
        available = [m for m in MODELS if m not in exhausted_models]
        if not available:
            print("   Daily limit reached on all models. Run the script again later.")
            return None
        model = available[attempt % len(available)]
        wait_for_slot()
        try:
            reply = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=VOICE),
            )
            return reply.text.strip()
        except Exception as error:
            message = str(error)
            print(f"   {model} failed: {message[:90]}")
            if "PerDay" in message:
                exhausted_models.add(model)
                print(f"   {model} is out of daily quota. Switching models...")
            elif "429" in message or "RESOURCE_EXHAUSTED" in message:
                print("   Hit the per-minute limit. Waiting 65 seconds...")
                time.sleep(65)
            else:
                wait = 15 * (attempt + 1)
                print(f"   Waiting {wait} seconds, then trying again...")
                time.sleep(wait)
    return None


# ---------- Part 4: save progress and results ----------

# ---------- Part 4: save progress and send for approval ----------

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def post_id_for(link):
    return hashlib.md5(link.encode()).hexdigest()[:10]


def main():
    items = top_items(3)
    cache = load_cache()

    for i, item in enumerate(items, start=1):
        link = item["link"]
        # write a draft if we have none, or if the saved one is from the old format
        if link not in cache or "[YOUR TAKE]" in cache[link]:
            print(f"Draft {i} of {len(items)}: writing - {item['title'][:60]}")
            text = draft(item)
            if text is None:
                print("Stopping early. Run the script again later; finished drafts are saved.")
                break
            cache[link] = text
            save_cache(cache)

        add_and_send(post_id_for(link), item["title"], cache[link], link)
        print(f"Draft {i}: sent to Telegram for approval")

    print("\nDone! Check Telegram.")


if __name__ == "__main__":
    main()