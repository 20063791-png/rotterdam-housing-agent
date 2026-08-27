import json
import csv
import asyncio
import re
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
# Configuration
# --------------------------------------------------

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

preferred = config["preferred_locations"]

# --------------------------------------------------
# Database
# --------------------------------------------------

if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()

# --------------------------------------------------
# Scoring
# --------------------------------------------------

def score_listing(city, price, rooms):

    score = 50

    city_points = {
        "Rotterdam":25,
        "Schiedam":20,
        "Delft":18,
        "Capelle aan den IJssel":16,
        "Vlaardingen":15,
        "Ridderkerk":12,
        "Barendrecht":10,
        "Dordrecht":8,
        "Spijkenisse":5
    }

    score += city_points.get(city,0)

    try:
        rent = int(re.sub(r"[^\d]","",price))
    except:
        rent = 99999

    if rent <= 1200:
        score += 20
    elif rent <= 1500:
        score += 15
    elif rent <= 1800:
        score += 8

    try:
        r = int(re.sub(r"[^\d]","",rooms))
        if 1 <= r <= 3:
            score += 10
    except:
        pass

    return min(score,100)

# --------------------------------------------------
# Extract property details
# --------------------------------------------------

async def extract_property(page,url,city):

    await page.goto(url,wait_until="domcontentloaded",timeout=60000)
    await page.wait_for_timeout(1500)

    title=""
    price=""
    rooms=""
    area=""
    agency=""

    try:
        title = await page.locator("h1").inner_text()
    except:
        pass

    try:
        body = await page.locator("body").inner_text()

        m = re.search(r"€[\d\.,]+",body)
        if m:
            price = m.group()

        m = re.search(r"(\d+)\s*rooms?",body,re.I)
        if m:
            rooms = m.group(1)

        m = re.search(r"(\d+)\s*m²",body)
        if m:
            area = m.group(1)

    except:
        pass

    try:
        agency = await page.locator("a[href*='/real-estate-agents/']").first.inner_text()
    except:
        pass

    score = score_listing(city,price,rooms)

    return {
        "city":city,
        "title":title or "See listing",
        "price":price or "Price on request",
        "rooms":rooms or "?",
        "area":area or "?",
        "agency":agency,
        "score":score,
        "url":url
    }

# --------------------------------------------------
# Scan city
# --------------------------------------------------

async def scan_city(browser,city):

    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent":"Mozilla/5.0"
    })

    slug = city.lower().replace(" ","-")
    url = f"{BASE}/apartments/{slug}"

    print(f"Scanning {city}...")

    listings=[]

    try:

        await page.goto(url,wait_until="domcontentloaded",timeout=60000)
        await page.wait_for_timeout(3000)

        links = await page.eval_on_selector_all(
            "a[href*='/apartment-for-rent/']",
            """
            els=>[...new Set(els.map(e=>e.href))]
            """
        )

        print(f"✓ {city}: {len(links)} listings")

        for link in links:

            if link in visited_urls:
                continue

            try:
                info = await extract_property(page,link,city)
                listings.append(info)
            except:
                pass

    except Exception as e:
        print(f"✗ {city}: {e}")

    await page.close()

    return listings

# --------------------------------------------------
# Main scan
# --------------------------------------------------

async def production_scan():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage"]
        )

        all_list=[]

        print("="*60)
        print("SCANNING ALL CITIES")
        print("="*60)

        for city in preferred:
            found = await scan_city(browser,city)
            all_list.extend(found)

        await browser.close()

        return all_list

# --------------------------------------------------
# Run
# --------------------------------------------------

all_listings = asyncio.run(production_scan())

# Remove duplicates
unique={}
for item in all_listings:
    unique[item["url"]] = item

new_listings = list(unique.values())

new_listings.sort(key=lambda x:x["score"],reverse=True)

# --------------------------------------------------
# Save tracker
# --------------------------------------------------

write_header = not TRACKER_FILE.exists()

with open(TRACKER_FILE,"a",newline="",encoding="utf-8") as f:

    writer=csv.writer(f)

    if write_header:
        writer.writerow([
            "Date",
            "City",
            "Title",
            "Price",
            "Rooms",
            "Area",
            "Agency",
            "Score",
            "URL"
        ])

    from datetime import datetime

    today=datetime.now().strftime("%Y-%m-%d %H:%M")

    for x in new_listings:

        writer.writerow([
            today,
            x["city"],
            x["title"],
            x["price"],
            x["rooms"],
            x["area"],
            x["agency"],
            x["score"],
            x["url"]
        ])

# --------------------------------------------------
# Telegram
# --------------------------------------------------

MAX_ALERTS=5

print("-"*60)
print(f"New listings : {len(new_listings)}")
print("-"*60)

print(f"Sending top {min(MAX_ALERTS,len(new_listings))} alerts...")

for item in new_listings[:MAX_ALERTS]:
    send_property_alert(item)

# --------------------------------------------------
# Update visited
# --------------------------------------------------

visited_urls.update(x["url"] for x in new_listings)

with open(VISITED_FILE,"w",encoding="utf-8") as f:
    json.dump(sorted(visited_urls),f,indent=2)

print("Database updated.")
