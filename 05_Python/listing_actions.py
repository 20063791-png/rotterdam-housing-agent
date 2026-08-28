import json
from pathlib import Path
from datetime import datetime, timedelta

# ==========================================================
# Listing Status Database
# ==========================================================

ROOT = Path(__file__).resolve().parent
DATABASE_DIR = ROOT / "Database"
DATABASE_DIR.mkdir(exist_ok=True)

STATUS_FILE = DATABASE_DIR / "listing_status.json"

# ----------------------------------------------------------
# Load database
# ----------------------------------------------------------

def load_status():

    if STATUS_FILE.exists():
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}

# ----------------------------------------------------------
# Save database
# ----------------------------------------------------------

def save_status(data):

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ----------------------------------------------------------
# Register listing
# ----------------------------------------------------------

def register_listing(listing):

    data = load_status()

    url = listing["url"]

    if url not in data:

        data[url] = {
            "title": listing["title"],
            "city": listing["city"],
            "price": listing.get("price", ""),
            "score": listing.get("score", 0),
            "status": "new",
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat()
        }

    else:

        data[url]["last_seen"] = datetime.now().isoformat()

    save_status(data)

# ----------------------------------------------------------
# Update status
# ----------------------------------------------------------

def set_status(url, status):

    data = load_status()

    if url in data:
        data[url]["status"] = status
        data[url]["updated"] = datetime.now().isoformat()

    save_status(data)

# ----------------------------------------------------------
# Read status
# ----------------------------------------------------------

def get_status(url):

    data = load_status()

    if url in data:
        return data[url]["status"]

    return "new"

# ----------------------------------------------------------
# Saved listings
# ----------------------------------------------------------

def get_saved_listings():

    data = load_status()

    return {

        url: item

        for url, item in data.items()

        if item["status"] == "saved"

    }

# ----------------------------------------------------------
# Expired listings (72h)
# ----------------------------------------------------------

def expire_old_saved():

    data = load_status()

    changed = False

    now = datetime.now()

    for url, item in data.items():

        if item["status"] != "saved":
            continue

        first_seen = datetime.fromisoformat(item["first_seen"])

        if now - first_seen >= timedelta(hours=72):

            item["status"] = "expired"
            item["expired"] = now.isoformat()

            changed = True

    if changed:
        save_status(data)

# ----------------------------------------------------------
# Rejects + Applied filter
# ----------------------------------------------------------

def should_skip(url):

    status = get_status(url)

    return status in ["applied", "rejected", "expired"]

# ----------------------------------------------------------
# Local test
# ----------------------------------------------------------

if __name__ == "__main__":

    test = {

        "title": "Test Apartment",
        "city": "Rotterdam",
        "price": "€950",
        "score": 81,
        "url": "https://example.com/test"

    }

    register_listing(test)

    print(load_status())
