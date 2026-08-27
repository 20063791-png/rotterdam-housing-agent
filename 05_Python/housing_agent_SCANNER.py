import json
import csv
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from telegram_listener import send_property_alert

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
# Scoring system
# --------------------------------------------------
def score_listing(url, city):
    score = 50

    city_scores = {
        "rotterdam": 35,
        "schiedam": 25,
        "delft": 25,
        "capelle aan den ijssel": 20,
        "vlaardingen": 15,
        "barendrecht": 15,
        "ridderkerk": 10,
        "spijkenisse": 10,
        "dordrecht": 5,
    }

    score += city_scores.get(city.lower(), 0)

    url_lower = url.lower()

    if "studio" in url_lower:
        score += 5
    if "house" in url_lower:
        score += 5
    if "woning" in url_lower:
        score += 5

    return min(score, 100)

# --------------------------------------------------
# Scan one city
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

        selectors = [
            "a[href*='/apartment-for-rent/']",
            "a[href*='/house-for-rent/']",
            "a[href*='/studio-for-rent/']",
            "a[href*='/for-rent/']"
        ]

        links = set()

        for selector in selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000)

                found = await page.eval_on_selector_all(
                    selector,
                    """
                    elements => elements.map(e =>
                        e.href.startsWith('http')
                            ? e.href
                            : 'https://www.pararius.com' + e.getAttribute('href')
                    )
                    """
                )

                links.update(found)

            except:
                pass

        listings = []

        for link in sorted(links):

            listings.append({
                "city": city,
                "title": Path(link).name.replace("-", " ").title(),
                "price": "See listing",
                "rooms": "?",
                "area": "?",
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
# Save new listings
# --------------------------------------------------
write_header = not TRACKER_FILE.exists()

with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if write_header:
        writer.writerow([
            "City",
            "Title",
            "Price",
            "Rooms",
            "Area",
            "Score",
            "URL"
        ])

    for item in new_listings:

        writer.writerow([
            item["city"],
            item["title"],
            item["price"],
            item["rooms"],
            item["area"],
            item["score"],
            item["url"]
        ])

# --------------------------------------------------
# Send Telegram alerts
# --------------------------------------------------
print("-" * 60)
print("Sending Telegram alerts...")

for item in new_listings:

    try:
        send_property_alert(item)
    except Exception as e:
        print(f"Telegram failed: {e}")

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
