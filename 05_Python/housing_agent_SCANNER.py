import json
import csv
import asyncio
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

from telegram_listener import send_property_alert
from filtering import filter_launch_listings

BASE = "https://www.pararius.com"

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "Config" / "config.json"
DATABASE_DIR = ROOT / "Database"

VISITED_FILE = DATABASE_DIR / "visited_urls.json"
TRACKER_FILE = DATABASE_DIR / "housing_tracker.csv"

DATABASE_DIR.mkdir(exist_ok=True)

# ==========================================================
# PRODUCTION MODE
# ==========================================================

DEBUG_SEND = False

# ==========================================================
# Load configuration
# ==========================================================

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ==========================================================
# Load visited URLs
# ==========================================================

if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()

# ==========================================================
# Smart scoring
# ==========================================================

def score_listing(city, text="", price_value=0, rooms=0, area=0):

    score = 0
    text = text.lower()

    # ---------------- City (20) ----------------

    city_points = {
        "rotterdam": 20,
        "schiedam": 18,
        "delft": 17,
        "capelle aan den ijssel": 15,
        "vlaardingen": 14,
        "barendrecht": 13,
        "ridderkerk": 12,
        "dordrecht": 10,
        "spijkenisse": 8
    }

    score += city_points.get(city.lower(), 8)

    # ---------------- Furnishing (30) ----------------

    if "furnished" in text:
        score += 30

    elif "upholstered" in text:
        score += 18

    # ---------------- Budget (30) ----------------

    if price_value:

        if price_value <= config["budget"]["room"]:
            score += 30

        elif price_value <= config["budget"]["studio"]:
            score += 27

        elif price_value <= config["budget"]["two_room"]:
            score += 24

        elif price_value <= config["budget"]["three_room"]:
            score += 18

        elif price_value <= config["filters"]["absolute_max_price"]:
            score += 10

    # ---------------- Registration (8) ----------------

    if "registration" in text:
        score += 8

    # ---------------- Area (7) ----------------

    if area >= 80:
        score += 7

    elif area >= 60:
        score += 5

    elif area >= 40:
        score += 4

    elif area >= config["filters"]["minimum_area"]:
        score += 2

    # ---------------- Nice-to-have (5) ----------------

    bonus = 0

    for word in ["balcony", "terrace", "garden"]:
        if word in text:
            bonus += 2

    score += min(bonus, 5)

    return min(score, 100)

# ==========================================================
# Real city detection (ONLY NEW PATCH)
# ==========================================================

async def get_listing_city(page, default_city):
    """
    Reads the actual city from the listing page.
    Falls back to the search city if not found.
    """

    try:
        body = (await page.text_content("body") or "").lower()

        cities = [
            "rotterdam",
            "schiedam",
            "delft",
            "capelle aan den ijssel",
            "vlaardingen",
            "barendrecht",
            "ridderkerk",
            "spijkenisse",
            "dordrecht"
        ]

        for city_name in cities:
            if city_name in body:
                return city_name.title()

    except Exception:
        pass

    return default_city

# ==========================================================
# Scan one city
# ==========================================================

async def scan_city(browser, city):

    page = await browser.new_page()
    page.set_default_timeout(8000)

    await page.set_extra_http_headers({
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36"
    })

    slug = city.lower().replace(" ", "-")

    # Search every property category
    search_urls = [

        f"{BASE}/apartments/{slug}",
        f"{BASE}/houses/{slug}",
        f"{BASE}/studios/{slug}",
        f"{BASE}/rooms/{slug}"

    ]

    print(f"Scanning {city}...")

    listings = []
    seen = set()

    try:

        for url in search_urls:

            try:

                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=10000
                )

                await page.wait_for_timeout(1200)

                cards = page.locator("a[href*='-for-rent/']")
                count = await cards.count()

                for i in range(count):

                    card = cards.nth(i)

                    try:

                        href = await card.get_attribute("href")

                        if not href:
                            continue

                        link = href if href.startswith("http") else BASE + href

                        if link in seen:
                            continue

                        seen.add(link)

                        # Keep exactly the same extraction logic

                        container = card.locator("xpath=ancestor::section[1]")

                        if await container.count() == 0:
                            container = card.locator("xpath=ancestor::article[1]")

                        if await container.count() == 0:
                            container = card.locator("xpath=..")

                        text = await container.inner_text()

                        slug_title = link.split("/")[-1]
                        title = slug_title.replace("-", " ").title()

                        # ---------------- Price ----------------

                        price = ""
                        price_value = 0

                        m = re.search(r"€\s*([\d.,]+)", text)

                        if m:
                            price = "€" + m.group(1)
                            price_value = int(
                                re.sub(r"[^\d]", "", m.group(1))
                            )

                        # ---------------- Rooms ----------------

                        rooms = 0

                        m = re.search(r"(\d+)\s*rooms?", text, re.I)

                        if m:
                            rooms = int(m.group(1))

                        # ---------------- Area ----------------

                        area = 0

                        m = re.search(r"(\d+)\s*m²", text)

                        if m:
                            area = int(m.group(1))

                        # ONLY CHANGE: detect the real city
                        real_city = await get_listing_city(page, city)

                        listings.append({

                            "city": real_city,
                            "title": title,
                            "price": price,
                            "price_value": price_value,
                            "rooms": rooms,
                            "area": area,
                            "score": score_listing(
                                real_city,
                                text,
                                price_value,
                                rooms,
                                area
                            ),
                            "url": link

                        })

                    except:
                        continue

            except:
                # Some cities simply won't have all categories.
                continue

        print(f"✓ {city}: {len(listings)} listings")

        await page.close()

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []

# ==========================================================
# Scan all cities
# ==========================================================

async def production_scan():

    async with async_playwright() as p:

        browser = await p.chromium.launch(

            headless=True,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        print("=" * 60)
        print("SCANNING ALL CITIES")
        print("=" * 60)

        tasks = [
            scan_city(browser, city)
            for city in config["preferred_locations"]
        ]

        results = await asyncio.gather(*tasks)

        all_listings = []

        for city_results in results:
            all_listings.extend(city_results)

        await browser.close()

    return all_listings

# ==========================================================
# Run scanner
# ==========================================================

all_listings = asyncio.run(production_scan())

if DEBUG_SEND:

    print("DEBUG MODE ENABLED - Ignoring visited database.")

    new_listings = all_listings.copy()

else:

    new_listings = [

        item
        for item in all_listings
        if item["url"] not in visited_urls

    ]

    new_listings = filter_launch_listings(
        new_listings,
        config
    )

new_listings.sort(
    key=lambda x: x["score"],
    reverse=True
)

# ==========================================================
# Quality check
# ==========================================================

print("=" * 60)
print("TOP 10 SCORED LISTINGS")
print("=" * 60)

if new_listings:

    for i, item in enumerate(new_listings[:10], 1):

        print(
            f"{i:>2}. "
            f"{item['score']:>3}/100 | "
            f"{item['city']:<12} | "
            f"{item['price']:<8} | "
            f"{item['rooms']}r | "
            f"{item['area']}m² | "
            f"{item['title']}"
        )

else:

    print("No listings available after filtering.")

# ==========================================================
# Summary
# ==========================================================

print("=" * 60)
print("SCAN SUMMARY")
print("=" * 60)

summary = {}

for item in all_listings:
    summary[item["city"]] = summary.get(item["city"], 0) + 1

for city in config["preferred_locations"]:
    print(f"{city:<24} {summary.get(city,0)}")

print("-" * 60)
print(f"Total listings found : {len(all_listings)}")
print(f"Known URLs           : {len(visited_urls)}")
print(f"Listings to send     : {len(new_listings)}")

# ==========================================================
# Telegram alerts
# ==========================================================

TOP_LIMIT = 10

print("-" * 60)
print(f"Sending top {min(len(new_listings), TOP_LIMIT)} alerts...")
print("-" * 60)

for i, listing in enumerate(new_listings[:TOP_LIMIT]):

    try:
        send_property_alert(listing, i)

    except Exception as e:
        print(f"Telegram failed: {listing['title']} ({e})")

# ==========================================================
# Save tracker
# ==========================================================

write_header = not TRACKER_FILE.exists()

with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if write_header:

        writer.writerow([

            "Date",
            "City",
            "Title",
            "Price",
            "Rooms",
            "Area",
            "Score",
            "URL"

        ])

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for item in new_listings:

        writer.writerow([

            now,
            item["city"],
            item["title"],
            item["price"],
            item["rooms"],
            item["area"],
            item["score"],
            item["url"]

        ])

# ==========================================================
# Update visited database
# ==========================================================

visited_urls.update(item["url"] for item in all_listings)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)

print("-" * 60)
print("Database updated.")
print(f"Tracker file: {TRACKER_FILE.name}")
print("-" * 60)
