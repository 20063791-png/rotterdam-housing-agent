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
# Search categories (safe expansion)
# ==========================================================

SEARCH_TYPES = [
    "apartments",
    "houses",
    "rooms"
]

# Studios are detected later from URLs/titles because
# Pararius doesn't expose a reliable studios search page.

# ==========================================================
# Load configuration
# ==========================================================

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# ==========================================================
# Load visited URLs
# ==========================================================

if VISITED_FILE.exists():
    visited_urls = set(json.loads(VISITED_FILE.read_text()))
else:
    visited_urls = set()

# ==========================================================
# Score (uses scanner values only)
# ==========================================================

def score_listing(city, title="", rooms=0, area=0):

    score = 0

    city_points = {
        "rotterdam":30,
        "schiedam":27,
        "delft":26,
        "capelle aan den ijssel":25,
        "vlaardingen":24,
        "barendrecht":23,
        "ridderkerk":22,
        "dordrecht":20,
        "spijkenisse":18
    }

    score += city_points.get(city.lower(),18)

    title_lower=title.lower()

    if "studio" in title_lower:
        score +=10

    if rooms in [1,2,3]:
        score +=8
    elif rooms>=4:
        score +=5

    if area>=60:
        score +=7
    elif area>=40:
        score +=5
    elif area>=config["filters"]["minimum_area"]:
        score +=3

    return min(score,100)

# ==========================================================
# Scan one city
# ==========================================================

async def scan_city(browser,city):

    page=await browser.new_page()

    page.set_default_timeout(8000)

    await page.set_extra_http_headers({
        "User-Agent":"Mozilla/5.0"
    })

    listings=[]
    seen=set()

    print(f"Scanning {city}...")

    slug=city.lower().replace(" ","-")

    try:

        for category in SEARCH_TYPES:

            url=f"{BASE}/{category}/{slug}"

            try:

                await page.goto(url,wait_until="domcontentloaded",timeout=10000)

                await page.wait_for_timeout(1200)

                cards=page.locator("a[href*='-for-rent/']")

                count=await cards.count()

                for i in range(count):

                    card=cards.nth(i)

                    href=await card.get_attribute("href")

                    if not href:
                        continue

                    link=href if href.startswith("http") else BASE+href

                    if link in seen:
                        continue

                    seen.add(link)

                    text=await card.locator("xpath=..").inner_text()

                    title=link.split("/")[-1].replace("-"," ").title()

                    rooms=0
                    area=0

                    m=re.search(r"(\d+)\s+rooms?",text,re.I)
                    if m:
                        rooms=int(m.group(1))

                    m=re.search(r"(\d+)\s*m²",text)
                    if m:
                        area=int(m.group(1))

                    listings.append({

                        "city":city,
                        "title":title,
                        "price":0,
                        "rooms":rooms,
                        "area":area,
                        "furnished":False,
                        "upholstered":False,
                        "score":score_listing(city,title,rooms,area),
                        "url":link

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

# ==========================================================
# Scan all cities
# ==========================================================

async def production_scan():

    async with async_playwright() as p:

        browser=await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        tasks=[
            scan_city(browser,c)
            for c in config["preferred_locations"]
        ]

        results=await asyncio.gather(*tasks)

        await browser.close()

    all_listings=[]

    for r in results:
        all_listings.extend(r)

    return all_listings

# ==========================================================
# Run
# ==========================================================

print("="*60)
print("SCANNING ALL CITIES")
print("="*60)

all_listings=asyncio.run(production_scan())

new_listings=[
    x for x in all_listings
    if x["url"] not in visited_urls
]

new_listings=filter_launch_listings(new_listings,config)

new_listings.sort(key=lambda x:x["score"],reverse=True)

# ==========================================================
# Debug
# ==========================================================

print("="*60)
print("TOP 10 SCORED LISTINGS")
print("="*60)

for x in new_listings[:10]:

    print(
        f"{x['score']:>3} | "
        f"{x['city']:<20} | "
        f"{x['rooms']}r | "
        f"{x['area']}m² | "
        f"{x['title']}"
    )

# ==========================================================
# Summary
# ==========================================================

summary={}

for x in all_listings:
    summary[x["city"]]=summary.get(x["city"],0)+1

print("="*60)
print("SCAN SUMMARY")
print("="*60)

for city in config["preferred_locations"]:
    print(f"{city:<24} {summary.get(city,0)}")

print("-"*60)
print(f"Total listings found : {len(all_listings)}")
print(f"Known URLs           : {len(visited_urls)}")
print(f"Listings to send     : {len(new_listings)}")

# ==========================================================
# Telegram
# ==========================================================

print("-"*60)
print(f"Sending top {min(10,len(new_listings))} alerts...")
print("-"*60)

for i,x in enumerate(new_listings[:10]):

    try:
        send_property_alert(x,i)
    except Exception as e:
        print(e)

# ==========================================================
# Save tracker
# ==========================================================

header=not TRACKER_FILE.exists()

with open(TRACKER_FILE,"a",newline="",encoding="utf-8") as f:

    w=csv.writer(f)

    if header:
        w.writerow([
            "Date","City","Title","Price","Rooms","Area","Score","URL"
        ])

    now=datetime.now().strftime("%Y-%m-%d %H:%M")

    for x in new_listings:

        w.writerow([
            now,
            x["city"],
            x["title"],
            x["price"],
            x["rooms"],
            x["area"],
            x["score"],
            x["url"]
        ])

visited_urls.update(x["url"] for x in all_listings)

VISITED_FILE.write_text(
    json.dumps(sorted(visited_urls),indent=2),
    encoding="utf-8"
)

print("-"*60)
print("Database updated.")
print(f"Tracker file: {TRACKER_FILE.name}")
print("-"*60)
