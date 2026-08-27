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
# Smart scoring (100-point system)
# ==========================================================

def score_listing(city, title="", rooms=0, area=0):

    score = 0

    city_points = {
        "rotterdam": 30,
        "schiedam": 27,
        "delft": 26,
        "capelle aan den ijssel": 25,
        "vlaardingen": 24,
        "barendrecht": 23,
        "ridderkerk": 22,
        "dordrecht": 18,
        "spijkenisse": 17
    }

    score += city_points.get(city.lower(), 15)

    title_lower = title.lower()

    # ------------------------------------------------------
    # Furnishing (highest priority)
    # ------------------------------------------------------

    if "furnished" in title_lower:
        score += 25

    elif "upholstered" in title_lower:
        score += 15

    else:
        score += 5

    # ------------------------------------------------------
    # Occupancy fit
    # ------------------------------------------------------

    if rooms == 0:
        score += 8

    elif rooms == 1:
        score += 15

    elif rooms == 2:
        score += 15

    elif rooms == 3:
        score += 15

    else:
        score += 12

    # ------------------------------------------------------
    # Area (small influence)
    # ------------------------------------------------------

    if area >= 90:
        score += 5

    elif area >= 70:
        score += 4

    elif area >= 50:
        score += 3

    elif area >= config["filters"]["minimum_area"]:
        score += 2

    # ------------------------------------------------------
    # Bonus keywords
    # ------------------------------------------------------

    bonuses = {
        "balcony": 2,
        "terrace": 2,
        "garden": 2,
        "renovated": 1,
        "new build": 1
    }

    for word, bonus in bonuses.items():
        if word in title_lower:
            score += bonus

    return min(score, 100)

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
    url = f"{BASE}/apartments/{slug}"

    print(f"Scanning {city}...")

    try:

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=10000
        )

        await page.wait_for_timeout(1500)

        cards = page.locator("a[href*='-for-rent/']")
        count = await cards.count()

        listings = []
        seen = set()

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

                text = await card.locator("xpath=..").inner_text()

                slug = link.split("/")[-1]
                title = slug.replace("-", " ").title()

                rooms = 0

                m = re.search(r"(\\d+)\\s+room", text, re.I)

                if m:
                    rooms = int(m.group(1))

                area = 0

                m = re.search(r"(\\d+)\\s*m²", text, re.I)

                if m:
                    area = int(m.group(1))

                listings.append({

                    "city": city,
                    "title": title,
                    "price": "",
                    "rooms": rooms,
                    "area": area,
                    "score": score_listing(city, title, rooms, area),
                    "url": link

                })

            except:
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
