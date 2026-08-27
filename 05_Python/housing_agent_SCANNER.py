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

if VISITED_FILE.exists():
    visited_urls = set(json.loads(VISITED_FILE.read_text(encoding="utf-8")))
else:
    visited_urls = set()

# ==========================================================
# Search categories
# ==========================================================

SEARCH_TYPES = [
    "apartments",
    "houses",
    "studios",
    "rooms"
]

# ==========================================================
# Scoring
# ==========================================================

def score_listing(city, price, furnished, upholstered, rooms, area, listing_type):

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

    budget = config["filters"]["maximum_price"]

    if price:

        ratio = price / budget

        if ratio <= 0.70:
            score += 30
        elif ratio <=0.85:
            score +=25
        elif ratio<=1:
            score +=18
        elif ratio<=1.10:
            score +=8

    if furnished:
        score +=20
    elif upholstered:
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

    if listing_type=="studio":
        score +=3

    return min(score,100)

# ==========================================================
# Extract one listing page
# ==========================================================

async def extract_listing(page,url,default_city):

    await page.goto(url,wait_until="domcontentloaded",timeout=10000)
    await page.wait_for_timeout(700)

    text = await page.text_content("body") or ""
    lower=text.lower()

    title=url.split("/")[-1].replace("-"," ").title()

    price=0
    rooms=0
    area=0

    m=re.search(r"€\s?([\d.,]+)",text)
    if m:
        price=int(m.group(1).replace(".","").replace(",",""))

    m=re.search(r"(\d+)\s+rooms?",text,re.I)
    if m:
        rooms=int(m.group(1))

    m=re.search(r"(\d+)\s*m²",text)
    if m:
        area=int(m.group(1))

    furnished="furnished" in lower or "gemeubileerd" in lower
    upholstered="upholstered" in lower or "gestoffeerd" in lower

    if "/studios/" in url or "studio" in lower:
        listing_type="studio"
    elif "/houses/" in url:
        listing_type="house"
    elif "/rooms/" in url:
        listing_type="room"
    else:
        listing_type="apartment"

    score=score_listing(
        default_city,
        price,
        furnished,
        upholstered,
        rooms,
        area,
        listing_type
    )

    return {
        "city":default_city,
        "title":title,
        "price":price,
        "rooms":rooms,
        "area":area,
        "furnished":furnished,
        "upholstered":upholstered,
        "type":listing_type,
        "score":score,
        "url":url
    }

# ==========================================================
# Scan one city
# ==========================================================

async def scan_city(browser,city):

    slug=city.lower().replace(" ","-")

    page=await browser.new_page()
    page.set_default_timeout(8000)

    urls=[]
    seen=set()

    print(f"Scanning {city}...")

    try:

        for category in SEARCH_TYPES:

            search=f"{BASE}/{category}/{slug}"

            try:

                await page.goto(search,wait_until="domcontentloaded",timeout=9000)
                await page.wait_for_timeout(600)

                links=await page.eval_on_selector_all(
                    "a[href*='-for-rent/']",
                    """
                    els=>[...new Set(
                        els.map(e=>e.href.startsWith("http")?e.href:"https://www.pararius.com"+e.getAttribute("href"))
                    )]
                    """
                )

                for link in links:
                    if link not in seen:
                        seen.add(link)
                        urls.append(link)

            except:
                pass

        listings=[]

        detail_page=await browser.new_page()
        detail_page.set_default_timeout(8000)

        for link in urls[:30]:

            try:
                listing=await extract_listing(detail_page,link,city)
                listings.append(listing)
            except:
                continue

        await detail_page.close()
        await page.close()

        print(f"✓ {city}: {len(listings)} listings")

        return listings

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return []

# ==========================================================
# Production scan
# ==========================================================

async def production_scan():

    async with async_playwright() as p:

        browser=await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage"]
        )

        tasks=[scan_city(browser,c) for c in config["preferred_locations"]]

        results=await asyncio.gather(*tasks)

        await browser.close()

    listings=[]

    for r in results:
        listings.extend(r)

    return listings

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
# Debug Top 10
# ==========================================================

print("="*60)
print("TOP 10 SCORED LISTINGS")
print("="*60)

for item in new_listings[:10]:

    print(
        f"{item['score']:>3} | "
        f"{item['city']:<20} | "
        f"€{item['price']:<5} | "
        f"{item['rooms']}r | "
        f"{item['area']}m² | "
        f"{item['title']}"
    )

# ==========================================================
# Summary
# ==========================================================

summary={}

for item in all_listings:
    summary[item["city"]]=summary.get(item["city"],0)+1

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

for i,item in enumerate(new_listings[:10]):

    try:
        send_property_alert(item,i)
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
            "Date","City","Title","Price","Rooms","Area",
            "Furnished","Score","Type","URL"
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
            x["furnished"],
            x["score"],
            x["type"],
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
