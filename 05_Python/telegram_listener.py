import os
import requests

BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
)

CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    "8674673640"
)


def build_ai_message(property_data):

    title = property_data.get("title","this property")
    city = property_data.get("city","the Netherlands")
    price = property_data.get("price","")

    return f"""Hi,

I am interested in {title} in {city}.

I am a researcher currently based in Italy and relocating to the Netherlands for my new position. I have a stable professional background and I am looking for a long-term place to rent.

The location and property fit my relocation plans very well, and I would appreciate the opportunity to arrange a viewing.

Thank you for your time and consideration.

Kind regards,

Grifton Muchovu
Researcher
"""


def send_property_alert(property_data,index):

    score = property_data.get("score",0)

    if score >= 90:
        badge="🔥 HIGH PRIORITY"
    elif score >=70:
        badge="⭐ STRONG MATCH"
    else:
        badge="📍 NEW LISTING"

    message=f"""
🏠 <b>Housing Agent v6</b>

<b>{badge}</b>

📍 <b>{property_data.get('title','')}</b>
🏙 {property_data.get('city','')}

💶 <b>{property_data.get('price','')}</b>
🛏 {property_data.get('rooms','?')} rooms
📐 {property_data.get('area','?')} m²

🎯 <b>Score: {score}/100</b>
"""

    keyboard={
        "inline_keyboard":[
            [
                {
                    "text":"🏡 Open Listing",
                    "url":property_data["url"]
                }
            ],
            [
                {
                    "text":"✍️ Copy AI Message",
                    "callback_data":f"message|{index}"
                }
            ],
            [
                {
                    "text":"🟢 Applied",
                    "callback_data":f"applied|{index}"
                },
                {
                    "text":"❌ Reject",
                    "callback_data":f"reject|{index}"
                }
            ]
        ]
    }

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":CHAT_ID,
            "text":message,
            "parse_mode":"HTML",
            "reply_markup":keyboard
        },
        timeout=20
    )
