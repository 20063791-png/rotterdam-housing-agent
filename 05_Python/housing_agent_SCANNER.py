import json
import csv
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://www.pararius.com"

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "Config" / "config.json"
DATABASE_DIR = ROOT / "Database"

VISITED_FILE = DATABASE_DIR / "visited_urls.json"
TRACKER_FILE = DATABASE_DIR / "housing_tracker.csv"

DATABASE_DIR.mkdir(exist_ok=True)

# --------------------------------------------------
# Load configuration
# --------------------------------------------------
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# --------------------------------------------------
# Load visited URLs
# --------------------------------------------------
if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()


# --------------------------------------------------
# Simple scoring (safe version)
# --------------------------------------------------
def score_listing(url, city):
    score = 0

    if city.lower() == "rotterdam":
        score += 20

    return score


# --------------------------------------------------
# Scan one city (WORKING VERSION)
# --------------------------------------------------
async def scan_city(browser, city):

    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
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

        await page.wait_for_selector(
            "a[href*='/apartment-for-rent/']",
            timeout=10000
        )

        links = await page.eval_on_selector_all(
            "a[href*='/apartment-for-rent/']",
            """
            elements => [...new Set(elements.map(e =>
                e.href.startsWith('http')
                    ? e.href
                    : 'https://www.pararius.com' + e.getAttribute('href')
            ))]
            """
        )

        listings = []

        for link in links:

            listings.append({
                "city": city,
                "title": "",
                "price": "",
                "rooms": "",
                "area": "",
                "score": score_listing(link, city),
                "url": link
            })

        print(f"✓ {city}: {len(listings)} listings")

        await page.close()

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []


# --------------------------------------------------
# Production scan
# --------------------------------------------------
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


# --------------------------------------------------
# Run scanner
# --------------------------------------------------
all_listings = asyncio.run(production_scan())

new_listings = [
    x for x in all_listings
    if x["url"] not in visited_urls
]

new_listings.sort(
    key=lambda x: x["score"],
    reverse=True
)

# --------------------------------------------------
# Summary
# --------------------------------------------------
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

# --------------------------------------------------
# Save new listings to Excel-compatible CSV
# --------------------------------------------------
write_header = not TRACKER_FILE.exists()

with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if write_header:
        writer.writerow([
            "City",
            "Score",
            "URL"
        ])

    for item in new_listings:

        writer.writerow([
            item["city"],
            item["score"],
            item["url"]
        ])

# --------------------------------------------------
# Update visited database
# --------------------------------------------------
visited_urls.update(item["url"] for item in all_listings)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)

print("-" * 60)
print("Database updated.")
print(f"Tracker file: {TRACKER_FILE.name}")
print("-" * 60)
