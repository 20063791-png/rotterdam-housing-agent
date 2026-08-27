import json
import csv
import asyncio
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

from telegram_listener import send_property_alert

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
# Stable scoring (Run #42)
# ==========================================================

def score_listing(city):

    score = 60

    city = city.lower()

    if city == "rotterdam":
        score += 20

    elif city in ["schiedam", "delft"]:
        score += 15

    elif city in [
        "capelle aan den ijssel",
        "vlaardingen",
        "barendrecht",
        "ridderkerk"
    ]:
        score += 10

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

        links = await page.eval_on_selector_all(
            "a[href*='-for-rent/']",
            """
            elements => [...new Set(
                elements
                    .map(e =>
                        e.href.startsWith('http')
                            ? e.href
                            : 'https://www.pararius.com'+e.getAttribute('href'))
                    .filter(h => h.includes('-for-rent/'))
            )]
            """
        )

        listings = []

        for link in links:

            slug = link.split("/")[-1]
            title = slug.replace("-", " ").title()

            listings.append({
                "city": city,
                "title": title,
                "price": "",
                "rooms": "",
                "area": "",
                "score": score_listing(city),
                "url": link
            })

        print(f"✓ {city}: {len(listings)} listings")

        await page.close()

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []

# ==========================================================
# Scan all cities (concurrent)
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
    item for item in all_listings
    if item["url"] not in visited_urls
]

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
print(f"New listings         : {len(new_listings)}")

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
