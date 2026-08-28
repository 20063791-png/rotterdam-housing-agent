import os
import re
import requests
import asyncio
from playwright.async_api import async_playwright

# ==========================================================
# Telegram Configuration (UNCHANGED)
# ==========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
CHAT_ID = os.getenv("CHAT_ID") or "8674673640"

# ==========================================================
# Get correct city from Pararius URL
# ==========================================================

def extract_city_from_url(url: str) -> str:
    """
    Extract city from Pararius URLs.

    apartment-for-rent/delft/...    -> Delft
    room-for-rent/schiedam/...      -> Schiedam
    house-for-rent/rotterdam/...    -> Rotterdam
    studio-for-rent/vlaardingen/... -> Vlaardingen
    """

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

            # ---------------- Price ----------------

            m = re.search(r"€\s?[\d.,]+", text)
            if m:
                details["price"] = m.group(0)

            # ---------------- Rooms ----------------

            m = re.search(r"(\d+)\s+rooms?", text, re.I)
            if m:
                details["rooms"] = m.group(1)

            # ---------------- Area ----------------

            m = re.search(r"(\d+)\s?m²", text)
            if m:
                details["area"] = m.group(1)

            # ---------------- Furnishing ----------------

            details["furnished"] = (
                "furnished" in lower or
                "gemeubileerd" in lower
            )

            details["upholstered"] = (
                "upholstered" in lower or
                "gestoffeerd" in lower
            )

            # ---------------- Quick Highlights ----------------

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

            # ---------------- First usable image ----------------

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
# AI Message Builder
# ==========================================================

def build_ai_message(property_data):

    return f"""Hello,

My name is Grifton Muchovu.

I am relocating to Rotterdam to work as a researcher at Erasmus MC on a long-term employment contract, and I am very interested in the property at {property_data['title']} in {property_data['city']}.

A little about me:

• Researcher at Erasmus MC
• Stable employment contract and reliable monthly income
• Non-smoker
• Quiet, clean and respectful tenant
• Looking for a long-term home
• Municipal registration (inschrijving) required
• References and proof of income available immediately

I value a peaceful and well-maintained home and always take good care of the place where I live.

I would be happy to arrange a viewing at your convenience.

Kind regards,

Grifton Muchovu
Erasmus MC Researcher"""


# ==========================================================
# Telegram Sender
# ==========================================================

def send_property_alert(property_data, index=0):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram configuration missing.")
        return

    details = asyncio.run(fetch_listing_details(property_data["url"]))

    # Always use city from URL

    city = extract_city_from_url(property_data["url"])

    property_for_ai = property_data.copy()
    property_for_ai["city"] = city

    # Prefer scanner values

    price = (
        f"€{property_data['price']}"
        if property_data.get("price")
        else details["price"] or "Price on listing"
    )

    rooms = (
        str(property_data["rooms"])
        if property_data.get("rooms")
        else details["rooms"]
    )

    area = (
        str(property_data["area"])
        if property_data.get("area")
        else details["area"]
    )

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

    if rooms:
        message += f"\n🛏 {rooms} room"

    if area:
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
            if x not in ["Furnished", "Upholstered"]
        ]

        if extras:
            message += "\n\n✨ " + " • ".join(extras)

    message += f"\n\n🔗 {property_data['url']}"

    # ======================================================
    # UPDATED BUTTONS
    # ======================================================

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
                    "callback_data": f"applied_{index}"
                },
                {
                    "text": "📌 Save Later",
                    "callback_data": f"save_{index}"
                }
            ],

            [
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject_{index}"
                }
            ]
        ]
    }

    # ======================================================
    # Try Photo First
    # ======================================================

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

        print(
            f"Photo failed for {property_data['title']}. "
            "Using text fallback."
        )

    # ======================================================
    # Guaranteed Text Fallback
    # ======================================================

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
