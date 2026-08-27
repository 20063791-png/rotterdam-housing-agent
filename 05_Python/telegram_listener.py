import os
import requests
from requests.utils import quote

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "8674673640"
)


def send_property_alert(property_data, property_index=0):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets missing.")
        return

    city = property_data.get("city", "Unknown")
    title = property_data.get("title", "Property")
    price = property_data.get("price", "See listing")
    rooms = property_data.get("rooms", "?")
    area = property_data.get("area", "?")
    score = property_data.get("score", 0)
    url = property_data.get("url", "")

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 70:
        priority = "⭐ STRONG MATCH"
    else:
        priority = "📍 NEW LISTING"

    message = f"""
🏠 <b>Housing Agent v5.1</b>

<b>{priority}</b>

📍 <b>{title}</b>
🏙 {city}

💶 <b>{price}</b>
🛏 {rooms} rooms
📐 {area} m²

🎯 <b>Score: {score}/100</b>

<a href="{url}">🏡 Open Listing</a>
"""

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✉️ AI Message",
                    "callback_data": f"message|{property_index}"
                }
            ],
            [
                {
                    "text": "✅ Applied",
                    "callback_data": f"applied|{property_index}"
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject|{property_index}"
                }
            ]
        ]
    }

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
            "disable_web_page_preview": False
        },
        timeout=20
    )

    if response.ok:
        print(f"Telegram sent: {title}")
    else:
        print(response.text)


if __name__ == "__main__":

    send_property_alert(
        {
            "city": "Rotterdam",
            "title": "Test Property",
            "price": "€1200",
            "rooms": 2,
            "area": 55,
            "score": 92,
            "url": "https://www.pararius.com"
        },
        0
    )
