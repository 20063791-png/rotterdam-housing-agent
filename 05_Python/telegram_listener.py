import os
import re
import hashlib
import requests
import asyncio
from playwright.async_api import async_playwright

# ==========================================================
# Telegram Configuration
# ==========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"
CHAT_ID = os.getenv("CHAT_ID") or "YOUR_CHAT_ID"

# ==========================================================
# Stable Property ID
# ==========================================================

def property_uid(url: str) -> str:
    """
    Generate a permanent ID from the URL.
    Only used if property_id does not already exist.
    """
    return hashlib.md5(url.encode()).hexdigest()[:8]

# ==========================================================
# Safe City Extractor
# ==========================================================

def get_city(property_data):

    city = str(property_data.get("city", "")).strip()

    if city and city.lower() != "nan":
        return city

    address = str(property_data.get("address", "")).strip()

    if address:

        for c in [
            "Rotterdam",
            "Schiedam",
            "Delft",
            "Ridderkerk",
            "Vlaardingen",
            "Barendrecht",
            "Spijkenisse",
            "Dordrecht",
            "Capelle aan den IJssel"
        ]:

            if c.lower() in address.lower():
                return c

    url = property_data["url"]

    m = re.search(
        r"/(?:apartment|room|house|studio)-for-rent/([^/]+)/",
        url.lower()
    )

    if m:
        return m.group(1).replace("-", " ").title()

    return "Unknown"

# ==========================================================
# Fast Property Detail Extractor
# ==========================================================

async def fetch_listing_details(url):

    details = {
        "price": "",
        "rooms": "",
        "area": "",
        "image": "",
        "summary": [],
        "furnished": False,
        "upholstered": False
    }

    try:

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox"]
            )

            page = await browser.new_page()
            page.set_default_timeout(6000)

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=8000
            )

            await page.wait_for_timeout(800)

            text = await page.text_content("body") or ""
            lower = text.lower()

            m = re.search(r"€\s?[\d.,]+", text)
            if m:
                details["price"] = m.group(0)

            m = re.search(r"(\d+)\s+rooms?", text, re.I)
            if m:
                details["rooms"] = m.group(1)

            m = re.search(r"(\d+)\s?m²", text)
            if m:
                details["area"] = m.group(1)

            details["furnished"] = (
                "furnished" in lower or
                "gemeubileerd" in lower
            )

            details["upholstered"] = (
                "upholstered" in lower or
                "gestoffeerd" in lower
            )

            keywords = {
                "balcony": "Balcony",
                "garden": "Garden",
                "terrace": "Terrace",
                "elevator": "Elevator",
                "parking": "Parking",
                "available immediately": "Available Now",
                "available now": "Available Now",
                "pets allowed": "Pets Allowed"
            }

            if details["furnished"]:
                details["summary"].append("Furnished")
            elif details["upholstered"]:
                details["summary"].append("Upholstered")

            for key, label in keywords.items():
                if key in lower:
                    details["summary"].append(label)

            details["summary"] = details["summary"][:3]

            imgs = await page.locator("img").evaluate_all("""
            imgs => imgs
                .map(i => i.src)
                .filter(s => s.startsWith("http"))
            """)

            for src in imgs:
                if "pararius" in src:
                    details["image"] = src
                    break

            if not details["image"] and imgs:
                details["image"] = imgs[0]

            await browser.close()

    except Exception:
        pass

    return details

# ==========================================================
# AI Message
# ==========================================================

def build_ai_message(property_data):

    return f"""Hello,

My name is Grifton Muchovu.

I am relocating to Rotterdam to work as a researcher at Erasmus MC and I am very interested in the property at {property_data['title']} in {property_data['city']}.

• Researcher at Erasmus MC
• Stable employment contract
• Reliable monthly income
• Non-smoker
• Looking for a long-term home
• Registration required
• References available

Kind regards,

Grifton Muchovu"""

# ==========================================================
# Telegram Sender
# ==========================================================

def send_property_alert(property_data, index=0):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram configuration missing.")
        return

    details = asyncio.run(fetch_listing_details(property_data["url"]))

    city = get_city(property_data)

    property_for_ai = property_data.copy()
    property_for_ai["city"] = city

    # ------------------------------------------------------
    # IMPORTANT FIX
    # ------------------------------------------------------

    uid = str(
        property_data.get(
            "property_id",
            property_uid(property_data["url"])
        )
    )

    print(f"Sending property: {uid}")

    price = (
        f"€{property_data['price']}"
        if property_data.get("price")
        else details["price"] or "Price on listing"
    )

    rooms = str(property_data.get("rooms") or details["rooms"])
    area = str(property_data.get("area") or details["area"])

    furnished = (
        property_data.get("furnished", False)
        or details["furnished"]
    )

    upholstered = (
        property_data.get("upholstered", False)
        or details["upholstered"]
    )

    score = property_data["score"]

    if score >= 90:
        priority = "🔥 HIGH PRIORITY"
    elif score >= 75:
        priority = "⭐ STRONG MATCH"
    else:
        priority = "📍 NEW LISTING"

    message = f"""🏠 <b>Housing Agent v12</b>

<b>{priority}</b>

📍 <b>{property_data['title']}</b>
🏙 {city}

💶 <b>{price}</b>"""

    if rooms and rooms != "None":
        message += f"\n🛏 {rooms} room"

    if area and area != "None":
        message += f"\n📐 {area} m²"

    if furnished:
        message += "\n🛋 Furnished"
    elif upholstered:
        message += "\n🪑 Upholstered"

    message += f"""

🎯 <b>Score: {score}/100</b>"""

    if details["summary"]:
        extras = [
            x for x in details["summary"]
            if x not in ["Furnished", "UpHolstered"]
        ]

        if extras:
            message += "\n\n✨ " + " • ".join(extras)

    message += f"\n\n🔗 {property_data['url']}"

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
                        build_ai_message(property_for_ai)
                }
            ],

            [
                {
                    "text": "🟢 Applied",
                    "callback_data": f"applied|{uid}"
                },
                {
                    "text": "📌 Save Later",
                    "callback_data": f"save|{uid}"
                }
            ],

            [
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject|{uid}"
                }
            ]
        ]
    }

    if details["image"]:

        photo_response = requests.post(
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

        if photo_response.ok:
            print(f"Telegram photo sent: {property_data['title']}")
            return

        print("Photo failed. Using text.")

    text_response = requests.post(
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

    if text_response.ok:
        print(f"Telegram text sent: {property_data['title']}")
    else:
        print(text_response.text)

# ==========================================================
# Local Test
# ==========================================================

if __name__ == "__main__":

    send_property_alert(
        {
            "property_id": "TEST1234",
            "title": "Test Property",
            "city": "Rotterdam",
            "score": 80,
            "price": 850,
            "rooms": 2,
            "area": 55,
            "furnished": True,
            "url": "https://www.pararius.com/room-for-rent/delft/test-property"
        }
    )
