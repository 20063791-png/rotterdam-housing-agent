import os
import requests

# ==========================================================
# Telegram Configuration
# ==========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
)

CHAT_ID = os.getenv(
    "CHAT_ID",
    "8674673640"
)

# ==========================================================
# AI Message Builder
# ==========================================================

def build_ai_message(property_data):

    return f"""Hello,

I am very interested in the property at {property_data['title']} ({property_data['city']}).

I am a Master's student at Erasmus University Rotterdam with stable financial support. I am responsible, non-smoking, and looking for a long-term home.

I would appreciate the opportunity to arrange a viewing.

Kind regards,
Grifton Muchovu"""

# ==========================================================
# Telegram Sender
# ==========================================================

def send_property_alert(property_data, index=0):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets missing.")
        return

    score = property_data["score"]

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 70:
        priority = "⭐ STRONG MATCH"
    else:
        priority = "📍 NEW LISTING"

    # Clean summary above the preview
    message = f"""🏠 <b>Housing Agent v10</b>

<b>{priority}</b>

📍 <b>{property_data['title']}</b>
🏙 {property_data['city']}

🎯 <b>Score: {score}/100</b>

🔗 {property_data['url']}"""

    keyboard = {
        "inline_keyboard": [

            [
                {
                    "text": "🏡 Open Listing",
                    "url": property_data["url"]
                }
            ],

            [
                {
                    "text": "✍️ Copy AI Message",
                    "switch_inline_query_current_chat":
                    build_ai_message(property_data)
                }
            ],

            [
                {
                    "text": "🟢 Applied",
                    "callback_data": f"applied_{index}"
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject_{index}"
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
        print(f"Telegram sent: {property_data['title']}")
    else:
        print(response.text)

# ==========================================================
# Local Test
# ==========================================================

if __name__ == "__main__":

    send_property_alert(
        {
            "title": "Test Property",
            "city": "Rotterdam",
            "score": 80,
            "url": "https://www.pararius.com"
        }
    )
