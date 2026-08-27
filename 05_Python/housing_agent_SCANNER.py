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

# ==================================================
# Load configuration
# ==================================================

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ==================================================
# Load visited URLs
# ==================================================

if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()

# ==================================================
# Scoring
# ==================================================

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

# ==================================================
# Extract property details
# ==================================================

async def extract_property_details(browser, link, city):

    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36"
    })

    try:

        await page.goto(
            link,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(1200)

        slug = link.split("/")[-1]

        title = slug.replace("-", " ").title()

        try:
            h1 = await page.locator("h1").first.inner_text()
            if h1.strip():
                title = h1.strip()
        except:
            pass

        price = ""

        price_selectors = [
            "[class*=price]",
            "[class*=rent]",
            "text=/€/"
        ]

        for selector in price_selectors:
            try:
                value = await page.locator(selector).first.inner_text()
                if value:
                    price = value.strip()
                    break
            except:
                pass

        rooms = ""

        room_selectors = [
            "text=/room/i",
            "[class*=room]"
        ]

        for selector in room_selectors:
            try:
                value = await page.locator(selector).first.inner_text()
                if value:
                    rooms = value.strip()
                    break
            except:
                pass

        area = ""

        area_selectors = [
            "text=/m²/i",
            "text=/sqm/i"
        ]

        for selector in area_selectors:
            try:
                value = await page.locator(selector).first.inner_text()
                if value:
                    area = value.strip()
                    break
            except:
                pass

        await page.close()

        return {
            "city": city,
            "title": title,
            "price": price,
            "rooms": rooms,
            "area": area,
            "score": score_listing(city),
            "url": link
        }

    except:

        await page.close()

        slug = link.split("/")[-1]

        return {
            "city": city,
            "title": slug.replace("-", " ").title(),
            "price": "",
            "rooms": "",
            "area": "",
            "score": score_listing(city),
            "url": link
        }

# ==================================================
# Scan one city
# ==================================================

async def scan_city(browser, city):

    page = await browser.new_page()

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
            timeout=60000
        )

        await page.wait_for_timeout(3000)

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

        await page.close()

        listings = []

        # Limit to first 20 per city to keep GitHub Actions fast
        for link in links[:20]:

            details = await extract_property_details(
                browser,
                link,
                city
            )

            listings.append(details)

        print(f"✓ {city}: {len(listings)} listings")

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []

# ==================================================
# Production Scan
# ==================================================

async def production_scan():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        all_listings = []

        print("=" * 60)
        print("SCANNING ALL CITIES")
        print("=" * 60)

        for city in config["preferred_locations"]:

            city_listings = await scan_city(browser, city)

            all_listings.extend(city_listings)

        await browser.close()

    return all_listings

# ==================================================
# Run Scanner
# ==================================================

all_listings = asyncio.run(production_scan())

new_listings = [
    item for item in all_listings
    if item["url"] not in visited_urls
]

new_listings.sort(
    key=lambda x: x["score"],
    reverse=True
)

# ==================================================
# Summary
# ==================================================

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

# ==================================================
# Telegram Alerts
# ==================================================

TOP_LIMIT = 10

print("-" * 60)
print(f"Sending top {min(len(new_listings), TOP_LIMIT)} alerts...")
print("-" * 60)

for i, listing in enumerate(new_listings[:TOP_LIMIT]):
    send_property_alert(listing, i)

# ==================================================
# Save Tracker
# ==================================================

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

# ==================================================
# Update Visited Database
# ==================================================

visited_urls.update(item["url"] for item in all_listings)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)

print("-" * 60)
print("Database updated.")
print("-" * 60)
