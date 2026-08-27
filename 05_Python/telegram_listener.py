import os
import requests

BOT_TOKEN = os.getenv("AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc")
CHAT_ID = os.getenv("8963641889")


def send_property_alert(property_data):
    """
    Sends a beautiful Telegram notification using HTML formatting.
    """

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets missing.")
        return

    city = property_data.get("city", "Unknown")
    title = property_data.get("title", "New Property")
    price = property_data.get("price", "N/A")
    rooms = property_data.get("rooms", "?")
    area = property_data.get("area", "?")
    score = property_data.get("score", 0)
    url = property_data.get("url")

    if score >= 80:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 60:
        priority = "⭐ GOOD MATCH"
    else:
        priority = "📌 NEW LISTING"

    message = f"""
<b>🏠 Housing Agent v4</b>

<b>{priority}</b>

📍 <b>{title}</b>
🏙 {city}

💶 <b>{price}</b>
🚪 {rooms} rooms
📐 {area} m²

🎯 <b>Score: {score}/100</b>

<a href="{url}">🔗 Open Listing</a>
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
