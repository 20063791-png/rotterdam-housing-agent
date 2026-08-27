import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "https://www.pararius.com"

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "Config" / "config.json"
DATABASE_DIR = ROOT / "Database"
VISITED_FILE = DATABASE_DIR / "visited_urls.json"

DATABASE_DIR.mkdir(exist_ok=True)

# Load configuration
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

# Load visited URLs
if VISITED_FILE.exists():
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_urls = set(json.load(f))
else:
    visited_urls = set()


async def scan_city(page, city):
    slug = city.lower().replace(" ", "-")
    url = f"{BASE}/apartments/{slug}"

    print(f"Scanning {city}...")

    try:
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        # Give the page a moment to render listings
        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_selector(
                "a[href*='/apartment-for-rent/']",
                timeout=15000
            )
        except Exception:
            print(f"✗ {city}: No apartment cards found.")
            return []

        links = await page.eval_on_selector_all(
            "a[href*='/apartment-for-rent/']",
            """
            elements => [...new Set(elements.map(e => e.href))]
            """
        )

        print(f"✓ {city}: {len(links)} listings")
        return links

    except Exception as e:
        print(f"✗ {city}: {e}")
        return []


async def production_scan():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        page = await browser.new_page()

        page.set_default_timeout(30000)

        await page.set_extra_http_headers({
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
        })

        all_links = {}

        print("=" * 60)
        print("SCANNING ALL CITIES")
        print("=" * 60)

        for city in config["preferred_locations"]:
            all_links[city] = await scan_city(page, city)

        await browser.close()

    return all_links


# ---------------- RUN SCANNER ----------------

all_city_links = asyncio.run(production_scan())

rental_links = sorted(set(
    link
    for city_links in all_city_links.values()
    for link in city_links
))

new_urls = [
    url
    for url in rental_links
    if url not in visited_urls
]

print("=" * 60)
print("SCAN SUMMARY")
print("=" * 60)

for city in config["preferred_locations"]:
    print(f"{city:<24} {len(all_city_links[city])}")

print("-" * 60)
print(f"Total listings found : {len(rental_links)}")
print(f"Known URLs           : {len(visited_urls)}")
print(f"New listings         : {len(new_urls)}")

# Save updated database
visited_urls.update(rental_links)

with open(VISITED_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(visited_urls), f, indent=2)
