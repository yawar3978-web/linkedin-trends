import os

import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_text(text):
    """Send a plain message to you."""
    requests.post(
        f"{BASE}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text[:4000]},
        timeout=20,
    )


def send_draft(post_id, title, text, link):
    """Send a draft with Approve / Reject buttons."""
    message = f"📝 {title}\n\n{text}\n\nSource: {link}"
    buttons = [[
        {"text": "✅ Approve", "callback_data": f"approve:{post_id}"},
        {"text": "❌ Reject", "callback_data": f"reject:{post_id}"},
    ]]
    r = requests.post(
        f"{BASE}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message[:4000],
            "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": buttons},
        },
        timeout=20,
    )
    return r.json()


if __name__ == "__main__":
    # A fake draft, just to test the buttons
    result = send_draft(
        "test1",
        "Test draft",
        "This is a fake post to check the buttons appear.",
        "https://example.com",
    )
    print("Sent!" if result.get("ok") else result)