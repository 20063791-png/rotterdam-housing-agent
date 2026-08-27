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
# 100-point scoring system
# ==========================================================

def score_listing(city, price=0, rooms=0, area=0,
                  furnished=False, upholstered=False):

    score = 0

    # -------------------------
    # Location (20)
    # -------------------------

    city_scores = {
        "rotterdam":20,
        "schiedam":18,
        "delft":18,
        "capelle aan den ijssel":15,
        "vlaardingen":14,
        "barendrecht":13,
        "ridderkerk":12,
        "dordrecht":8,
        "spijkenisse":7
    }

    score += city_scores.get(city.lower(),5)

    # -------------------------
    # Budget fit (30)
    # -------------------------

    if price:

        if price <= 700:
            score += 30

        elif price <= 850:
            score += 27

        elif price <= 1000:
            score += 24

        elif price <= 1200:
            score += 20

        elif price <= 1400:
            score += 15

        elif price <= 1800:
            score += 8

        elif price <= 2500:
            score += 3

    else:
        score += 10

    # -------------------------
    # Furnishing (20)
    # -------------------------

    if furnished:
        score += 20

    elif upholstered:
        score += 12

    # -------------------------
    # Occupancy fit (15)
    # -------------------------

    if rooms in [1,2,3]:
        score += 15

    elif rooms==0:
        score += 8

    else:
        score += 12

    # -------------------------
    # Area (10)
    # -------------------------

    if area>=70:
        score +=10

    elif area>=50:
        score +=8

    elif area>=30:
        score +=5

    elif area>=config["filters"]["minimum_area"]:
        score +=3

    # -------------------------
    # Nice-to-have (5)
    # -------------------------

    if furnished:
        score +=2

    return min(score,100)

# ==========================================================
# Scan one city
# ==========================================================

async def scan_city(browser, city):

    page=await browser.new_page()
    page.set_default_timeout(8000)

    await page.set_extra_http_headers({

        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    })

    slug=city.lower().replace(" ","-")
    url=f"{BASE}/apartments/{slug}"

    print(f"Scanning {city}...")

    try:

        await page.goto(url,
                        wait_until="domcontentloaded",
                        timeout=10000)

        await page.wait_for_timeout(1500)

        cards=page.locator("a[href*='-for-rent/']")
        count=await cards.count()

        listings=[]
        seen=set()

        for i in range(count):

            card=cards.nth(i)

            try:

                href=await card.get_attribute("href")

                if not href:
                    continue

                link=href if href.startswith("http") else BASE+href

                if link in seen:
                    continue

                seen.add(link)

                text=await card.locator("xpath=..").inner_text()

                slug=link.split("/")[-1]
                title=slug.replace("-"," ").title()

                # -------------------------
                # Real city from URL
                # -------------------------

                parts=link.split("/")

                city_slug=parts[-2] if len(parts)>=2 else city

                detected_city=city_slug.replace("-"," ").title()

                # -------------------------
                # Price
                # -------------------------

                price=0

                m=re.search(r"€\s*([\d.,]+)",text)

                if m:
                    digits=re.sub(r"[^\d]","",m.group(1))
                    if digits:
                        price=int(digits)

                # -------------------------
                # Rooms
                # -------------------------

                rooms=0

                m=re.search(r"(\d+)\s*room",text,re.I)

                if m:
                    rooms=int(m.group(1))

                # -------------------------
                # Area
                # -------------------------

                area=0

                m=re.search(r"(\d+)\s*m²",text,re.I)

                if m:
                    area=int(m.group(1))

                # -------------------------
                # Furnishing
                # -------------------------

                lower=text.lower()

                furnished=("furnished" in lower or
                            "gemeubileerd" in lower)

                upholstered=("upholstered" in lower or
                              "gestoffeerd" in lower)

                listings.append({

                    "city":detected_city,
                    "title":title,
                    "price":price,
                    "rooms":rooms,
                    "area":area,
                    "furnished":furnished,
                    "upholstered":upholstered,
                    "score":score_listing(

                        detected_city,
                        price,
                        rooms,
                        area,
                        furnished,
                        upholstered

                    ),
                    "url":link

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

        browser=await p.chromium.launch(

            headless=True,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        print("="*60)
        print("SCANNING ALL CITIES")
        print("="*60)

        tasks=[scan_city(browser,c)
               for c in config["preferred_locations"]]

        results=await asyncio.gather(*tasks)

        all_listings=[]

        for r in results:
            all_listings.extend(r)

        await browser.close()

    return all_listings

# ==========================================================
# Run scanner
# ==========================================================

all_listings=asyncio.run(production_scan())

# Sort ALL listings for debugging
all_listings.sort(key=lambda x:x["score"],reverse=True)

print("="*60)
print("TOP 10 SCORED LISTINGS")
print("="*60)

for x in all_listings[:10]:

    price=f"€{x['price']}" if x["price"] else "Unknown"

    furn=" Furnished" if x["furnished"] else (
        " Upholstered" if x["upholstered"] else "")

    print(
        f"{x['score']:>3} | {x['city']:<15} | "
        f"{price:<8} | {x['rooms']}r | "
        f"{x['area']}m² | {x['title']}{furn}"
    )

# Production only
new_listings=[
    x for x in all_listings
    if x["url"] not in visited_urls
]

new_listings=filter_launch_listings(new_listings,config)

new_listings.sort(key=lambda x:x["score"],reverse=True)

# ==========================================================
# Summary
# ==========================================================

print("="*60)
print("SCAN SUMMARY")
print("="*60)

summary={}

for item in all_listings:
    summary[item["city"]]=summary.get(item["city"],0)+1

for city in config["preferred_locations"]:
    print(f"{city:<24} {summary.get(city,0)}")

print("-"*60)
print(f"Total listings found : {len(all_listings)}")
print(f"Known URLs           : {len(visited_urls)}")
print(f"Listings to send     : {len(new_listings)}")

# ==========================================================
# Telegram alerts
# ==========================================================

TOP_LIMIT=10

print("-"*60)
print(f"Sending top {min(len(new_listings),TOP_LIMIT)} alerts...")
print("-"*60)

for i,listing in enumerate(new_listings[:TOP_LIMIT]):

    try:
        send_property_alert(listing,i)

    except Exception as e:
        print(f"Telegram failed: {listing['title']} ({e})")

# ==========================================================
# Save tracker
# ==========================================================

write_header=not TRACKER_FILE.exists()

with open(TRACKER_FILE,"a",newline="",encoding="utf-8") as f:

    writer=csv.writer(f)

    if write_header:

        writer.writerow([
            "Date","City","Title","Price",
            "Rooms","Area","Score","URL"
        ])

    now=datetime.now().strftime("%Y-%m-%d %H:%M")

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

visited_urls.update(x["url"] for x in all_listings)

with open(VISITED_FILE,"w",encoding="utf-8") as f:
    json.dump(sorted(visited_urls),f,indent=2)

print("-"*60)
print("Database updated.")
print(f"Tracker file: {TRACKER_FILE.name}")
print("-"*60)
