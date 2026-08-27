import requests

# ==================================================
# HARDCODED TELEGRAM SETTINGS (FOR TESTING)
# ==================================================
BOT_TOKEN = "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
CHAT_ID = "8674673640"


def send_property_alert(property_data):
    """Send a clean Telegram notification."""

    city = property_data.get("city", "Unknown")
    title = property_data.get("title", "New Property")
    price = property_data.get("price", "N/A")
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
🏠 <b>Housing Agent v4</b>

<b>{priority}</b>

📍 <b>{title}</b>
🏙 {city}

💶 <b>{price}</b>
🛏 {rooms} rooms
📐 {area} m²

🎯 <b>Score: {score}/100</b>

<a href="{url}">🏡 Open Listing</a>
"""

    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )

    if response.ok:
        print(f"Telegram sent: {title}")
    else:
        print(f"Telegram error: {response.text}")


# ==================================================
# CONNECTION TEST
# ==================================================
if __name__ == "__main__":
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": "✅ Housing Agent Telegram test successful."
        },
        timeout=20,
    )

    print(response.text)
