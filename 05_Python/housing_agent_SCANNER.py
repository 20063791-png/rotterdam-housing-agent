# ==========================================================
# CELL 5 - PRODUCTION MULTI-CITY SCANNER (FINAL)
# One fresh browser page per city
# ==========================================================

import nest_asyncio
nest_asyncio.apply()

import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

BASE = "https://www.pararius.com"

async def scan_city(browser, city):

    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
    })

    try:

        await page.goto(
            f"{BASE}/apartments/{city}",
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(4000)

        html = await page.content()

        soup = BeautifulSoup(html, "html.parser")

        links = []

        for a in soup.find_all("a", href=True):

            href = a["href"]

            if href.startswith("/apartment-for-rent/"):
                links.append(BASE + href)

            elif href.startswith("https://www.pararius.com/apartment-for-rent/"):
                links.append(href)

        links = sorted(set(links))

        print(f"✓ {city:<24} {len(links):>3} listings")

        await page.close()

        return city, links

    except Exception as e:

        print(f"✗ {city}: {e}")

        await page.close()

        return city, []


async def production_scan():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage"]
        )

        all_links = {}

        print("="*60)
        print("SCANNING ALL CITIES")
        print("="*60)

        for city in config["cities"]:

            _, links = await scan_city(browser, city)

            all_links[city] = links

        await browser.close()

    return all_links


# ---------------- RUN ----------------

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

print("\n"+"="*60)
print("SCAN SUMMARY")
print("="*60)

for city in config["cities"]:
    print(f"{city:<24} {len(all_city_links[city]):>3}")

print("-"*60)

print(f"Total listings found : {len(rental_links)}")
print(f"Known URLs           : {len(visited_urls)}")
print(f"New listings         : {len(new_urls)}")