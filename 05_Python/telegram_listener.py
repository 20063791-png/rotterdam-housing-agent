import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8674673640")


def send_property_alert(property_data, index):

    city = property_data.get("city", "")
    title = property_data.get("title", "Property")
    price = property_data.get("price", "")
    rooms = property_data.get("rooms", "")
    area = property_data.get("area", "")
    score = property_data.get("score", 0)
    url = property_data.get("url", "")

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 70:
        priority = "⭐ STRONG MATCH"
    else:
        priority = "📍 NEW LISTING"

    message = f"""🏠 <b>Housing Agent v7</b>

{priority}

📍 <b>{title}</b>
🏙 {city}
"""

    if price and price != "See listing":
        message += f"\n💶 <b>{price}</b>"

    if rooms not in ["", "?"]:
        message += f"\n🛏 {rooms} rooms"

    if area not in ["", "?"]:
        message += f"\n📐 {area} m²"

    message += f"""

🎯 <b>Score: {score}/100</b>
"""

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🏡 Open Listing",
                    "url": url
                }
            ],
            [
                {
                    "text": "✍️ Copy AI Message",
                    "callback_data": f"message|{index}"
                }
            ],
            [
                {
                    "text": "🟢 Applied",
                    "callback_data": f"applied|{index}"
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject|{index}"
                }
            ]
        ]
    }

    requests.post(
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
