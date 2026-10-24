import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"

updates = requests.get(f"{BASE}/getUpdates", timeout=20).json()
messages = [u["message"] for u in updates.get("result", []) if "message" in u]

if not messages:
    print("No messages found. Open your bot in Telegram, send 'hi', then run this again.")
else:
    chat_id = messages[-1]["chat"]["id"]
    print("Your chat id is:", chat_id)
    requests.post(
        f"{BASE}/sendMessage",
        json={"chat_id": chat_id, "text": "Hello from your LinkedIn pipeline!"},
        timeout=20,
    )
    print("Test message sent. Check Telegram.")