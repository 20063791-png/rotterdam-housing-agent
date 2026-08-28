from pathlib import Path
import json
import requests
import pandas as pd
import os
import re
from datetime import datetime

from callback_utils import finish_message
from status_manager import update_listing

ROOT = Path(__file__).resolve().parent

CONFIG = ROOT / "Config/config.json"
TRACKER = ROOT / "Database/housing_tracker.csv"
LOG = ROOT / "Database/applications_log.csv"

print("=" * 60)
print("TELEGRAM CALLBACK HANDLER STARTED")
print("=" * 60)

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]

tracker = pd.read_csv(TRACKER)

print(f"Tracker contains {len(tracker)} listings.")

# ------------------------------------------------------------
# Load log
# ------------------------------------------------------------

if LOG.exists():
    log = pd.read_csv(LOG)
else:
    log = pd.DataFrame(columns=[
        "time",
        "url",
        "title",
        "price",
        "decision",
        "status"
    ])

# ------------------------------------------------------------
# Read Telegram updates
# ------------------------------------------------------------

response = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
    timeout=20
)

updates = response.json()

print(f"Telegram HTTP Status: {response.status_code}")
print(f"Updates received: {len(updates.get('result', []))}")

processed = 0

# ------------------------------------------------------------
# City helper
# ------------------------------------------------------------

def get_city(prop):

    if "city" in tracker.columns:

        city = str(prop.get("city", "")).strip()

        if city and city.lower() != "nan":
            return city

    title = str(prop.get("title", ""))

    m = re.search(
        r"(Rotterdam|Schiedam|Delft|Ridderkerk|Vlaardingen|Barendrecht|Spijkenisse|Dordrecht|Capelle aan den IJssel)",
        title,
        re.IGNORECASE
    )

    if m:
        return m.group(1).title()

    return "Unknown"

# ------------------------------------------------------------
# Callback acknowledgement
# ------------------------------------------------------------

def answer(callback_id, text):

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={
            "callback_query_id": callback_id,
            "text": text
        },
        timeout=20
    )

# ------------------------------------------------------------
# Process callbacks
# ------------------------------------------------------------

for item in updates.get("result", []):

    callback = item.get("callback_query")

    if callback is None:
        continue

    print("-" * 50)
    print("Button press detected.")

    data = callback["data"]

    print(f"Callback data: {data}")

    action = None
    prop = None

    # ========================================================
    # NEW UUID FORMAT
    # action|listing_id
    # ========================================================

    if "|" in data:

        action, listing_id = data.split("|", 1)

        print(f"UUID: {listing_id}")

        if "listing_id" not in tracker.columns:

            print("listing_id column missing.")
            answer(callback["id"], "System needs updating.")
            continue

        match = tracker[tracker["listing_id"].astype(str) == listing_id]

        if match.empty:

            print("Listing ID not found.")
            answer(callback["id"], "Listing no longer exists.")
            continue

        index = match.index[0]
        prop = tracker.loc[index]

    # ========================================================
    # OLD INDEX FORMAT
    # action_index
    # ========================================================

    elif "_" in data:

        action, index = data.split("_", 1)

        try:
            index = int(index)
        except Exception:
            print("Invalid callback index.")
            continue

        if index >= len(tracker):
            print("Index outside tracker.")
            continue

        prop = tracker.loc[index]

    else:

        print("Unknown callback format.")
        continue

    chat = callback["message"]["chat"]["id"]
    msg = callback["message"]["message_id"]

    url = str(prop.get("url", ""))
    title = str(prop.get("title", "Unknown Property"))
    city = get_city(prop)

    print(f"Listing: {title}")
    print(f"City: {city}")

    answer(callback["id"], "Processing...")

    current = str(prop.get("status", "")).strip()

    if current in ["Applied", "Rejected"]:

        answer(callback["id"], f"Already {current.lower()}.")
        print("Already completed.")
        continue

    # ---------------- Applied ----------------

    if action == "applied":

        tracker.loc[prop.name, "status"] = "Applied"

        update_listing(url, "Applied")

        log.loc[len(log)] = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            url,
            title,
            prop.get("price", ""),
            "Applied",
            "Completed"
        ]

        finish_message(chat, msg, title, city, "Applied")

        answer(callback["id"], "Applied!")

    # ---------------- Saved ----------------

    elif action == "save":

        tracker.loc[prop.name, "status"] = "Saved"

        update_listing(url, "Saved")

        finish_message(chat, msg, title, city, "Saved")

        answer(callback["id"], "Saved!")

    # ---------------- Rejected ----------------

    elif action == "reject":

        tracker.loc[prop.name, "status"] = "Rejected"

        update_listing(url, "Rejected")

        finish_message(chat, msg, title, city, "Rejected")

        answer(callback["id"], "Rejected!")

    else:

        answer(callback["id"], "Unknown action.")
        continue

    processed += 1

# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

tracker.to_csv(TRACKER, index=False)
log.to_csv(LOG, index=False)

# ------------------------------------------------------------
# Clear processed updates
# ------------------------------------------------------------

if updates.get("result"):

    last = max(u["update_id"] for u in updates["result"])

    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"offset": last + 1},
        timeout=20
    )

print("-" * 50)
print(f"Processed {processed} callbacks.")
print("=" * 60)
