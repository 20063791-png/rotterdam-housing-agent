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
# Scoring
# --------------------------------------------------


def score_listing(city, price, rooms, area):

    score = 50

    city = city.lower()

    if city == "rotterdam":
        score += 20
    elif city in ["schiedam", "delft"]:
        score += 15
    elif city in ["capelle aan den ijssel", "vlaardingen"]:
        score += 10

    if isinstance(price, int):
        if price <= 1200:
            score += 20
        elif price <= 1500:
            score += 10

    if isinstance(area, int):
        if area >= 45:
            score += 10

    if isinstance(rooms, int):
        if rooms >= 2:
            score += 10

    return min(score, 100)

# --------------------------------------------------
# Scan one city
# --------------------------------------------------


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

        await page.wait_for_timeout(2500)

        await page.wait_for_selector(
            "a[href*='-for-rent/'], a[href*='/apartment-for-rent/']",
            timeout=15000
        )

        cards = await page.query_selector_all(
            "section.search-list__item, div.search-list__item, article"
        )

        listings = []

        seen = set()

        if cards:

            for card in cards:

                link = await card.query_selector(
                    "a[href*='-for-rent/'], a[href*='/apartment-for-rent/']"
                )

                if not link:
                    continue

                href = await link.get_attribute("href")

                if not href:
                    continue

                full_url = href if href.startswith(
                    "http") else BASE + href

                if full_url in seen:
                    continue

                seen.add(full_url)

                title = ""
                price = ""
                rooms = "?"
                area = "?"

                try:
                    title = (await link.inner_text()).strip()
                except:
                    pass

                try:
                    text = (await card.inner_text()).replace("\n", " ")

                    import re

                    p = re.search(r"€\s*([\d.,]+)", text)
                    if p:
                        price = "€" + p.group(1)

                    r = re.search(r"(\d+)\s*rooms?", text, re.I)
                    if r:
                        rooms = int(r.group(1))

                    a = re.search(r"(\d+)\s*m²", text)
                    if a:
                        area = int(a.group(1))

                except:
                    pass

                price_number = None
                if price:
                    try:
                        price_number = int(
                            price.replace("€", "")
                            .replace(".", "")
                            .replace(",", "")
                        )
                    except:
                        pass

                score = score_listing(
                    city,
                    price_number,
                    rooms if isinstance(rooms, int) else None,
                    area if isinstance(area, int) else None
                )

                listings.append({
                    "city": city,
                    "title": title if title else "See listing",
                    "price": price if price else "See listing",
                    "rooms": rooms,
                    "area": area,
                    "score": score,
                    "url": full_url
                })

        else:

            links = await page.eval_on_selector_all(
                "a[href*='-for-rent/'], a[href*='/apartment-for-rent/']",
                """
                elements => [...new Set(elements.map(e=>e.href))]
                """
            )

            for link in links:

                listings.append({
                    "city": city,
                    "title": "See listing",
                    "price": "See listing",
                    "rooms": "?",
                    "area": "?",
                    "score": score_listing(city, None, None, None),
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

            listings = await scan_city(browser, city)

            all_listings.extend(listings)

        await browser.close()

    return all_listings

# --------------------------------------------------
# Run scan
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

print("-" * 60)
print(f"New listings : {len(new_listings)}")
print("-" * 60)

# --------------------------------------------------
# Telegram
# --------------------------------------------------

TOP_LIMIT = 10

print(f"Sending top {min(len(new_listings),TOP_LIMIT)} alerts...")

for item in new_listings[:TOP_LIMIT]:
    send_property_alert(item)

# --------------------------------------------------
# Save tracker
# --------------------------------------------------

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

    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    for item in new_listings:

        writer.writerow([
            today,
            item["city"],
            item["title"],
            item["price"],
            item["rooms"],
            item["area"],
            item["score"],
            item["url"]
        ])

# --------------------------------------------------
# Update visited
# --------------------------------------------------

visited_urls.update(item["url"] for item in all_listings)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)

print("Database updated.")
