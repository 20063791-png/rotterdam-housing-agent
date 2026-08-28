from pathlib import Path
import json
import requests
import os

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "Config/config.json"

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

BOT_TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]


def finish_message(chat_id, message_id, title, city, status):
    """
    Update the original Telegram card after a button press.
    Falls back to a new confirmation message if editing fails.
    """

    icons = {
        "Applied": "🟢",
        "Rejected": "❌",
        "Saved": "📌"
    }

    text = (
        f"🏠 <b>Housing Agent v12</b>\n\n"
        f"{icons.get(status,'📍')} <b>{status} ✓</b>\n\n"
        f"<b>{title}</b>\n"
        f"🏙 {city}\n\n"
    )

    if status == "Applied":
        text += "Application recorded.\nRemoved from future alerts."

    elif status == "Rejected":
        text += "Listing removed.\nWon't appear again."

    elif status == "Saved":
        text += "Reminder scheduled.\nDaily at 21:00 for up to 72 hours."

    print("-" * 60)
    print("Editing Telegram message...")
    print(f"Chat ID   : {chat_id}")
    print(f"Message ID: {message_id}")
    print(f"Status    : {status}")
    print(f"Property  : {title}")

    try:

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=20
        )

        print(f"HTTP Status: {response.status_code}")

        try:
            result = response.json()
            print("Telegram response:")
            print(json.dumps(result, indent=2))
        except Exception:
            print(response.text)

        if response.ok:
            print("Message updated successfully.")
            return True

        print("editMessageText failed. Sending fallback message.")

    except Exception as e:
        print(f"Telegram edit failed: {e}")

    # ----------------------------------------------------------
    # FALLBACK
    # ----------------------------------------------------------

    try:

        fallback = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            timeout=20
        )

        print(f"Fallback HTTP Status: {fallback.status_code}")

        if fallback.ok:
            print("Fallback confirmation sent.")
            return True

        print(fallback.text)

    except Exception as e:
        print(f"Fallback failed: {e}")

    return False
