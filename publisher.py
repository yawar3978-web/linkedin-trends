import sys
from datetime import date

from approvals import check_approvals, save_queue
from linkedin_helpers import days_left, post_to_linkedin
from telegram_helpers import send_text

DRY_RUN = len(sys.argv) > 1 and sys.argv[1] == "dry"


def main():
    queue = check_approvals()  # reads your Approve / Reject taps from Telegram
    left = days_left()

    # Warn you about the LinkedIn token (at most once per day)
    today = str(date.today())
    if left is not None and left <= 7 and queue.get("last_warning") != today:
        if left > 0:
            send_text(f"⚠️ Your LinkedIn token expires in {left} day(s). "
                      "Generate a new one in the LinkedIn developer portal.")
        else:
            send_text("⛔ Your LinkedIn token has expired. Posting is paused until "
                      "you generate a new one.")
        queue["last_warning"] = today
        save_queue(queue)

    if left is not None and left <= 0:
        print("Token expired, not posting.")
        return

    for post_id, post in queue["posts"].items():
        if post["status"] != "approved":
            continue
        if post_id.startswith("test"):
            continue  # never publish test drafts

        if DRY_RUN:
            print("WOULD POST:", post["title"])
            continue

        text = post["text"] + "\n\nSource: " + post["link"]
        try:
            ok, info = post_to_linkedin(text)
        except Exception as error:
            ok, info = False, str(error)[:200]

        if ok:
            post["status"] = "posted"
            post["linkedin_id"] = info
            send_text(f"🚀 Posted to LinkedIn: {post['title'][:80]}")
            print("Posted:", post["title"])
        else:
            post["attempts"] = post.get("attempts", 0) + 1
            print("Post failed:", info)
            if post["attempts"] >= 3:
                post["status"] = "failed"
                send_text(f"❌ Could not post '{post['title'][:60]}' after 3 tries: {info[:200]}")
        save_queue(queue)

    print("Done.")


if __name__ == "__main__":
    main()