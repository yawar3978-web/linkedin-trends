import os
import re
from datetime import date, datetime

import requests
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")
TOKEN_DATE = os.getenv("LINKEDIN_TOKEN_DATE")  # e.g. 2026-10-24
LINKEDIN_VERSION = "202609"  # if LinkedIn complains about the version, try "202608"
TOKEN_LIFETIME_DAYS = 60


def days_left():
    """How many days until your LinkedIn token expires (None if date is missing)."""
    if not TOKEN_DATE:
        return None
    start = datetime.strptime(TOKEN_DATE, "%Y-%m-%d").date()
    return TOKEN_LIFETIME_DAYS - (date.today() - start).days


def headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Linkedin-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def get_member_urn():
    """Ask LinkedIn who you are. Posts need your member id as the 'author'."""
    r = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        timeout=20,
    )
    r.raise_for_status()
    return "urn:li:person:" + r.json()["sub"]


def escape_text(text):
    """LinkedIn treats some characters as special codes and cuts the post off.
    A backslash in front of them makes LinkedIn show them normally.
    (The # sign is left alone so hashtags still work.)"""
    return re.sub(r"([\\|{}@\[\]()<>*_~])", r"\\\1", text)


def post_to_linkedin(text, visibility="PUBLIC"):
    """Publish a text post to your own profile. Returns (ok, message)."""
    body = {
        "author": get_member_urn(),
        "commentary": escape_text(text),
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers(),
        json=body,
        timeout=30,
    )
    if r.status_code == 201:
        return True, r.headers.get("x-restli-id", "posted")
    return False, f"{r.status_code}: {r.text[:300]}"


if __name__ == "__main__":
    left = days_left()
    print("Token days left:", left)
    ok, info = post_to_linkedin(
        "Test post from my automation project (please ignore). #DataScience",
        visibility="CONNECTIONS",
    )
    print("Posted!" if ok else "Failed:", info)