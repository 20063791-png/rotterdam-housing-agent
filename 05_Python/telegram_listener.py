from pathlib import Path
import json
import os
import re
import asyncio
import requests
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "Config/config.json"

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

BOT_TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]
CHAT_ID = os.getenv("CHAT_ID") or cfg["telegram"]["chat_id"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ==========================================================
# Get correct city from Pararius URL
# ==========================================================

def extract_city_from_url(url: str) -> str:
    """
    Extract city from Pararius URLs.

    apartment-for-rent/delft/...      -> Delft
    room-for-rent/schiedam/...        -> Schiedam
    house-for-rent/rotterdam/...      -> Rotterdam
    studio-for-rent/vlaardingen/...   -> Vlaardingen
    """

    m = re.search(
        r"/(?:apartment|room|house|studio)-for-rent/([^/]+)/",
        url,
        re.IGNORECASE
    )

    if m:
        city = m.group(1).replace("-", " ")
        return city.title()

    return "Unknown"


# ==========================================================
# Fast Property Detail Extractor
# ==========================================================

async def fetch_listing_details(url):

    details = {
        "photo": "",
        "area": "",
        "rooms": "",
        "title": ""
    }

    try:

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)

            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Photo
            try:
                img = await page.locator("img").first.get_attribute("src")
                if img:
                    details["photo"] = img
            except:
                pass

            text = await page.locator("body").inner_text()

            # Area
            m = re.search(r"(\d+)\s*m²", text)
            if m:
                details["area"] = m.group(1)

            # Rooms
            m = re.search(r"(\d+)\s+rooms?", text, re.IGNORECASE)
            if m:
                details["rooms"] = m.group(1)

            # Title
            try:
                details["title"] = await page.title()
            except:
                pass

            await browser.close()

    except Exception as e:
        print(f"Detail extraction failed: {e}")

    return details


# ==========================================================
# AI Message Builder
# ==========================================================

def build_ai_message(property_data):

    return f"""Hi,

I found this rental opportunity that looks worth checking.

🏠 {property_data.get('title','Rental listing')}

📍 {property_data.get('city','Unknown')}
💶 €{property_data.get('price','?')}
🛏 {property_data.get('rooms','?')} rooms
📐 {property_data.get('area','?')} m²

{property_data.get('url','')}

Kind regards,

Grifton Muchovu
Erasmus MC Researcher"""


# ==========================================================
# Telegram Sender
# ==========================================================

def send_property_alert(property_data, index=0):

    details = asyncio.run(fetch_listing_details(property_data["url"]))

    # Always use city from URL
    city = extract_city_from_url(property_data["url"])

    property_for_ai = property_data.copy()
    property_for_ai["city"] = city

    # Prefer scanner values
    price = (
        f"€{property_data['price']}"
        if property_data.get("price")
        else "€?"
    )

    rooms = property_data.get("rooms") or details["rooms"] or "?"
    area = property_data.get("area") or details["area"] or "?"
    score = property_data.get("score", 0)

    if score >= 80:
        badge = "🔥 PERFECT MATCH"
    elif score >= 70:
        badge = "✨ STRONG MATCH"
    elif score >= 60:
        badge = "👍 GOOD MATCH"
    else:
        badge = "🏠 NEW LISTING"

    title = property_data.get("title") or details["title"] or "Rental Listing"

    message = (
        f"🏠 <b>Housing Agent v12</b>\n\n"
        f"{badge}\n\n"
        f"📍 <b>{title}</b>\n"
        f"🏙 {city}\n\n"
        f"💶 {price}\n"
        f"🛏 {rooms} room\n"
        f"📐 {area} m²\n\n"
        f"🎯 <b>Score: {score}/100</b>"
    )

    message += f"\n\n🔗 {property_data['url']}"

    # ======================================================
    # SIMPLE STABLE BUTTONS ONLY
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
                    "text": "📋 Copy All Message",
                    "switch_inline_query_current_chat": build_ai_message(property_for_ai)
                }
            ]

        ]
    }

    photo = details["photo"]

    print("-" * 50)
    print(f"Sending property: {title}")

    # Try photo first

    if photo:

        response = requests.post(
            f"{API}/sendPhoto",
            json={
                "chat_id": CHAT_ID,
                "photo": photo,
                "caption": message,
                "parse_mode": "HTML",
                "reply_markup": keyboard
            },
            timeout=30
        )

        if response.ok:
            return True

        print("Photo failed. Using text.")
        print(response.text)

    # Fallback text

    text_response = requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": keyboard
        },
        timeout=30
    )

    if text_response.ok:
        print("Text message sent.")
        return True
    else:
        print(text_response.text)
        return False


# ==========================================================
# Local Test
# ==========================================================

if __name__ == "__main__":

    sample = {
        "title": "Flat for rent: Test Street",
        "price": 1200,
        "rooms": 2,
        "area": 55,
        "score": 75,
        "url": "https://www.pararius.com/apartment-for-rent/rotterdam/test"
    }

    send_property_alert(sample)
