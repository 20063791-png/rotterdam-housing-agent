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
    Update the original Telegram message after a button is pressed.
    Works for both photo messages and text messages.
    Removes buttons and sends a confirmation message.
    """

    icons = {
        "Applied": "🟢",
        "Rejected": "❌",
        "Saved": "📌"
    }

    descriptions = {
        "Applied": "Application recorded.\nRemoved from future alerts.",
        "Rejected": "Listing removed.\nWon't appear again.",
        "Saved": "Reminder scheduled.\nDaily at 21:00 for up to 72 hours."
    }

    icon = icons.get(status, "✅")

    text = (
        f"🏠 <b>Housing Agent v12</b>\n\n"
        f"{icon} <b>{status} ✓</b>\n\n"
        f"<b>{title}</b>\n"
        f"🏙 {city}\n\n"
        f"{descriptions.get(status, '')}"
    )

    # ----------------------------------------------------------
    # First try updating PHOTO messages (most listings are photos)
    # ----------------------------------------------------------

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": []}
        },
        timeout=20
    )

    # ----------------------------------------------------------
    # If it wasn't a photo message, update as TEXT instead
    # ----------------------------------------------------------

    if not response.ok:

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": []}
            },
            timeout=20
        )

    # ----------------------------------------------------------
    # Always send a confirmation notification
    # ----------------------------------------------------------

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"{icon} {status}: {title}"
        },
        timeout=20
    )
