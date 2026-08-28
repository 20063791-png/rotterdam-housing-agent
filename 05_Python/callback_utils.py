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

    icons = {
        "Applied": "🟢",
        "Rejected": "❌",
        "Saved": "📌"
    }

    text = (
        f"🏠 <b>Housing Agent v12</b>\n\n"
        f"{icons[status]} <b>{status} ✓</b>\n\n"
        f"<b>{title}</b>\n"
        f"🏙 {city}\n\n"
    )

    if status == "Applied":
        text += "Application recorded.\nRemoved from future alerts."

    elif status == "Rejected":
        text += "Listing removed.\nWon't appear again."

    else:
        text += "Reminder scheduled.\nDaily at 21:00 for up to 72 hours."

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        },
        timeout=20
    )
