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
# Application log
# ------------------------------------------------------------

if LOG.exists():
    log = pd.read_csv(LOG)
else:
    log = pd.DataFrame(columns=[
        "time",
        "property_id",
        "listing_url",
        "title",
        "price",
        "decision",
        "status"
    ])

# ------------------------------------------------------------
# Telegram updates
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
# Safe city extractor
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
        return m.group(1)

    return "Unknown"

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

    # NEW FORMAT:
    # applied|08c06a37

    if "|" not in data:
        print("Invalid callback format.")
        continue

    action, property_id = data.split("|", 1)

    # --------------------------------------------------------
    # Find listing by property_id
    # --------------------------------------------------------

    match = tracker[tracker["property_id"] == property_id]

    if match.empty:
        print(f"Property not found: {property_id}")

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            json={
                "callback_query_id": callback["id"],
                "text": "Listing no longer exists."
            },
            timeout=20
        )

        continue

    index = match.index[0]
    prop = match.iloc[0]

    chat = callback["message"]["chat"]["id"]
    msg = callback["message"]["message_id"]

    title = str(prop.get("title", "Unknown Property"))

    city = get_city(prop)

    url = prop.get("listing_url", prop.get("url", ""))

    print(f"Property ID: {property_id}")
    print(f"Listing: {title}")
    print(f"City: {city}")

    # --------------------------------------------------------
    # Immediate acknowledgement
    # --------------------------------------------------------

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={
            "callback_query_id": callback["id"],
            "text": "Processing..."
        },
        timeout=20
    )

    current_status = str(prop.get("status", "")).strip()

    if current_status in ["Applied", "Rejected"]:

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            json={
                "callback_query_id": callback["id"],
                "text": f"Already {current_status.lower()}."
            },
            timeout=20
        )

        continue

    # --------------------------------------------------------
    # APPLIED
    # --------------------------------------------------------

    if action == "applied":

        tracker.loc[index, "status"] = "Applied"

        update_listing(url, "Applied")

        log.loc[len(log)] = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            property_id,
            url,
            title,
            prop.get("price", ""),
            "Applied",
            "Completed"
        ]

        finish_message(
            chat,
            msg,
            title,
            city,
            "Applied"
        )

        print("Applied processed.")

    # --------------------------------------------------------
    # REJECT
    # --------------------------------------------------------

    elif action == "reject":

        tracker.loc[index, "status"] = "Rejected"

        update_listing(url, "Rejected")

        finish_message(
            chat,
            msg,
            title,
            city,
            "Rejected"
        )

        print("Rejected processed.")

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    elif action == "save":

        tracker.loc[index, "status"] = "Saved"

        update_listing(url, "Saved")

        finish_message(
            chat,
            msg,
            title,
            city,
            "Saved"
        )

        print("Saved processed.")

    else:

        print(f"Unknown action: {action}")
        continue

    processed += 1

# ------------------------------------------------------------
# Save tracker
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
