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
# Load application log
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
# Safe city extractor
# ------------------------------------------------------------

def get_city(prop):
    """
    Return city safely even if tracker has no city column.
    """

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
# Telegram helper
# ------------------------------------------------------------

def answer_callback(callback_id, text="Processing..."):
    """
    Safely answer callback so Telegram immediately shows feedback.
    """

    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": text
            },
            timeout=20
        )
    except Exception as e:
        print(f"Callback acknowledgement failed: {e}")

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

    if "_" not in data:
        print("Invalid callback format.")
        continue

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

    chat = callback["message"]["chat"]["id"]
    msg = callback["message"]["message_id"]

    url = str(prop.get("url", ""))
    title = str(prop.get("title", "Unknown Property"))
    city = get_city(prop)
    price = prop.get("price", "")

    print(f"Listing: {title}")
    print(f"City: {city}")
    print(f"Current Status: {prop.get('status','')}")

    # --------------------------------------------------------
    # Immediate acknowledgement
    # --------------------------------------------------------

    answer_callback(callback["id"], "⏳ Processing...")

    current_status = str(prop.get("status", "")).strip()

    # --------------------------------------------------------
    # Prevent duplicate actions
    # --------------------------------------------------------

    if current_status in ["Applied", "Rejected"]:

        answer_callback(
            callback["id"],
            f"Already {current_status.lower()}."
        )

        print(f"Already {current_status}.")
        continue

    # --------------------------------------------------------
    # APPLIED
    # --------------------------------------------------------

    if action == "applied":

        tracker.loc[index, "status"] = "Applied"

        update_listing(url, "Applied")

        log.loc[len(log)] = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            url,
            title,
            price,
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

        answer_callback(callback["id"], "✅ Applied!")

        print("Applied processed.")

    # --------------------------------------------------------
    # REJECTED
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

        answer_callback(callback["id"], "❌ Rejected!")

        print("Rejected processed.")

    # --------------------------------------------------------
    # SAVED
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

        answer_callback(callback["id"], "📌 Saved!")

        print("Saved processed.")

    # --------------------------------------------------------
    # Unknown action
    # --------------------------------------------------------

    else:

        print(f"Unknown action: {action}")
        answer_callback(callback["id"], "Unknown action.")

    processed += 1

# ------------------------------------------------------------
# Save tracker
# ------------------------------------------------------------

tracker.to_csv(TRACKER, index=False)
log.to_csv(LOG, index=False)

# ------------------------------------------------------------
# Clear processed Telegram updates
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
