import json
import os
import sys

import requests

from telegram_helpers import BASE, CHAT_ID, send_draft, send_text

QUEUE_FILE = "queue.json"


def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"offset": 0, "posts": {}}


def save_queue(queue):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def add_and_send(post_id, title, text, link):
    """Put a draft in the queue and send it to Telegram for approval."""
    queue = load_queue()
    if post_id in queue["posts"]:
        return  # already sent before
    result = send_draft(post_id, title, text, link)
    if result.get("ok"):
        queue["posts"][post_id] = {
            "title": title,
            "text": text,
            "link": link,
            "status": "pending",
        }
        save_queue(queue)
    else:
        print("Telegram send failed:", result)


def answer_tap(callback_id, text):
    """Make the little spinner on the button stop and show a short note."""
    requests.post(
        f"{BASE}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=20,
    )


def remove_buttons(message):
    requests.post(
        f"{BASE}/editMessageReplyMarkup",
        json={
            "chat_id": message["chat"]["id"],
            "message_id": message["message_id"],
            "reply_markup": {"inline_keyboard": []},
        },
        timeout=20,
    )


def check_approvals():
    """Read your button taps from Telegram and update the queue."""
    queue = load_queue()
    updates = requests.get(
        f"{BASE}/getUpdates",
        params={"offset": queue["offset"], "timeout": 0},
        timeout=20,
    ).json()

    for update in updates.get("result", []):
        queue["offset"] = update["update_id"] + 1  # mark as read
        tap = update.get("callback_query")
        if not tap:
            continue
        if str(tap["from"]["id"]) != str(CHAT_ID):
            continue  # ignore anyone who is not you

        action, _, post_id = tap["data"].partition(":")
        post = queue["posts"].get(post_id)

        if post is None:
            answer_tap(tap["id"], "Unknown draft")
        elif post["status"] != "pending":
            answer_tap(tap["id"], f"Already {post['status']}")
        else:
            post["status"] = "approved" if action == "approve" else "rejected"
            answer_tap(tap["id"], post["status"].capitalize())
            remove_buttons(tap["message"])
            if post["status"] == "approved":
                send_text(f"✅ Approved: {post['title'][:80]}")
            else:
                send_text(f"❌ Rejected: {post['title'][:80]}")

    save_queue(queue)
    return queue


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        add_and_send(
            "test-approval-1",
            "Test draft",
            "This is a fake post to test the approval flow.",
            "https://example.com",
        )
        print("Test draft sent. Tap a button in Telegram, then run: python approvals.py")
    else:
        queue = check_approvals()
        for post_id, post in queue["posts"].items():
            print(f"{post['status']:10} {post['title'][:60]}")