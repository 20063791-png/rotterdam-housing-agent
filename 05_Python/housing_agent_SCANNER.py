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

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()


# -----------------------------
# Score listings
# -----------------------------
def score_listing(price, rooms, area):
    score = 0

    try:
        p = int("".join(c for c in price if c.isdigit()))
    except:
        p = 999999

    try:
        r = int(rooms)
    except:
        r = 0

    try:
        a = int(area)
    except:
        a = 0

    if p <= 1200:
        score += 40
    elif p <= 1500:
        score += 25
    elif p <= 1800:
        score += 10

    if r >= 2:
        score += 25
    elif r == 1:
        score += 15

    if a >= 60:
        score += 20
    elif a >= 40:
        score += 10

    return score


# -----------------------------
# Scan one city
# -----------------------------
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

        cards = await page.locator("section.search-list__item").all()

        if len(cards) == 0:
            cards = await page.locator("article").all()

        listings = []

        for card in cards:

            try:

                title = await card.locator("a[href*='/apartment-for-rent/']").first.inner_text(timeout=500)
                href = await card.locator("a[href*='/apartment-for-rent/']").first.get_attribute("href")

                if not href:
                    continue

                if href.startswith("/"):
                    href = BASE + href

                text = await card.inner_text()

                price = ""
                rooms = ""
                area = ""

                import re

                p = re.search(r"€[\d,.]+", text)
                if p:
                    price = p.group()

                r = re.search(r"(\d+)\s+rooms?", text)
                if r:
                    rooms = r.group(1)

                a = re.search(r"(\d+)\s*m²", text)
                if a:
                    area = a.group(1)

                score = score_listing(price, rooms, area)

                listings.append({
                    "city": city,
                    "title": title,
                    "price": price,
                    "rooms": rooms,
                    "area": area,
                    "score": score,
                    "url": href
                })

            except:
                continue

        await page.close()

        print(f"✓ {city}: {len(listings)} listings")

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []


# -----------------------------
# Production scan
# -----------------------------
async def production_scan():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
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


# -----------------------------
# Run
# -----------------------------
all_listings = asyncio.run(production_scan())

new_listings = [
    x for x in all_listings
    if x["url"] not in visited_urls
]

new_listings.sort(key=lambda x: x["score"], reverse=True)

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

# -----------------------------
# Save tracker CSV
# -----------------------------
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

# -----------------------------
# Update visited database
# -----------------------------
visited_urls.update(x["url"] for x in all_listings)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)
