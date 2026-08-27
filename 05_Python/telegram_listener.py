import os
import requests

# Read from GitHub Secrets first, then fall back to hardcoded values
BOT_TOKEN = os.getenv("BOT_TOKEN", "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc")
CHAT_ID = os.getenv("CHAT_ID", "8963641889")


def send_property_alert(property_data):
    """
    Send a clean HTML Telegram notification.
    """

    if BOT_TOKEN == "AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc" or CHAT_ID == "8963641889":
        print("Telegram secrets missing.")
        return

    city = property_data.get("city", "Unknown")
    title = property_data.get("title", "New Property")
    price = property_data.get("price", "N/A")
    rooms = property_data.get("rooms", "?")
    area = property_data.get("area", "?")
    score = property_data.get("score", 0)
    url = property_data.get("url", "")

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 75:
        priority = "⭐ STRONG MATCH"
    elif score >= 60:
        priority = "✅ GOOD MATCH"
    else:
        priority = "🆕 NEW LISTING"

    message = f"""
<b>🏡 Housing Agent v4</b>

<b>{priority}</b>

📍 <b>{title}</b>
🏙️ {city}

💶 <b>{price}</b>
🛏️ {rooms} rooms
📐 {area} m²

🎯 <b>Score: {score}/100</b>

<a href="{url}">🏠 Open Listing</a>
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
