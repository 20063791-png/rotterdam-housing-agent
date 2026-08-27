import os
import json
import re
import requests
import asyncio
from playwright.async_api import async_playwright

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
# Fast Property Detail Extractor
# ==========================================================

async def fetch_listing_details(url):

    details = {
        "price": "",
        "rooms": "",
        "area": "",
        "image": ""
    }

    try:

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            page = await browser.new_page()

            page.set_default_timeout(5000)

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=8000
            )

            await page.wait_for_timeout(800)

            # ==================================================
            # First try Pararius JSON-LD
            # ==================================================

            scripts = await page.locator(
                "script[type='application/ld+json']"
            ).all_text_contents()

            for script in scripts:

                try:

                    data = json.loads(script)

                    text = json.dumps(data)

                    # Price

                    m = re.search(r'"price"\s*:\s*"?(\\d+)"?', text)

                    if m and not details["price"]:
                        details["price"] = f"€{m.group(1)}"

                    # Area

                    m = re.search(
                        r'"floorSize".*?"value"\s*:\s*(\\d+)',
                        text
                    )

                    if m and not details["area"]:
                        details["area"] = m.group(1)

                    # Image

                    if isinstance(data, dict) and "image" in data:

                        if isinstance(data["image"], list):
                            details["image"] = data["image"][0]

                        elif isinstance(data["image"], str):
                            details["image"] = data["image"]

                except Exception:
                    pass

            # ==================================================
            # Fallback to visible page text
            # ==================================================

            body = await page.text_content("body")

            if not details["price"]:

                m = re.search(r"€\s?[\d.,]+", body)

                if m:
                    details["price"] = m.group(0)

            if not details["rooms"]:

                m = re.search(r"(\\d+)\\s+rooms?", body, re.I)

                if m:
                    details["rooms"] = m.group(1)

            if not details["area"]:

                m = re.search(r"(\\d+)\\s?m²", body)

                if m:
                    details["area"] = m.group(1)

            # ==================================================
            # Fallback image
            # ==================================================

            if not details["image"]:

                try:

                    img = await page.locator("img").first.get_attribute("src")

                    if img and img.startswith("http"):
                        details["image"] = img

                except Exception:
                    pass

            await browser.close()

    except Exception:
        pass

    return details

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

    details = asyncio.run(fetch_listing_details(property_data["url"]))

    price = details["price"] or "Price on listing"

    rooms = details["rooms"]
    area = details["area"]

    score = property_data["score"]

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 70:
        priority = "⭐ STRONG MATCH"
    else:
        priority = "📍 NEW LISTING"

    message = f"""🏠 <b>Housing Agent v9</b>

<b>{priority}</b>

📍 <b>{property_data['title']}</b>
🏙 {property_data['city']}

💶 <b>{price}</b>"""

    if rooms:
        message += f"\n🛏 {rooms} rooms"

    if area:
        message += f"\n📐 {area} m²"

    message += f"""

🎯 <b>Score: {score}/100</b>"""

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

    # ==================================================
    # Send with image if available
    # ==================================================

    if details["image"]:

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": CHAT_ID,
                "photo": details["image"],
                "caption": message,
                "parse_mode": "HTML",
                "reply_markup": keyboard
            },
            timeout=20
        )

    else:

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
