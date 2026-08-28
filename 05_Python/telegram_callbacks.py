from pathlib import Path
import json
import requests
import pandas as pd
import os
from datetime import datetime

from callback_utils import finish_message
from status_manager import update_listing

ROOT = Path(__file__).resolve().parent

CONFIG = ROOT / "Config/config.json"
TRACKER = ROOT / "Database/housing_tracker.csv"
LOG = ROOT / "Database/applications_log.csv"

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]

print("=" * 60)
print("TELEGRAM CALLBACK HANDLER STARTED")
print("=" * 60)

tracker = pd.read_csv(TRACKER)
print(f"Tracker contains {len(tracker)} listings.")

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

# ---------------------------------------------------------
# Download Telegram updates
# ---------------------------------------------------------

response = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
    timeout=20
)

print(f"Telegram HTTP Status: {response.status_code}")

updates = response.json()

print(f"Updates received: {len(updates.get('result', []))}")

processed = 0

# ---------------------------------------------------------
# Process callbacks
# ---------------------------------------------------------

for item in updates.get("result", []):

    callback = item.get("callback_query")

    if callback is None:
        continue

    print("-" * 50)
    print("Button press detected.")

    data = callback.get("data", "")
    print(f"Callback data: {data}")

    if "_" not in data:
        print("Invalid callback format.")
        continue

    action, index = data.split("_", 1)

    try:
        index = int(index)
    except Exception:
        print("Could not convert callback index.")
        continue

    if index >= len(tracker):
        print(f"Index {index} outside tracker.")
        continue

    prop = tracker.loc[index]

    chat = callback["message"]["chat"]["id"]
    msg = callback["message"]["message_id"]
    url = prop["url"]

    print(f"Listing: {prop['title']}")
    print(f"City: {prop['city']}")
    print(f"Action: {action}")

    # --------------------------------------------
    # Immediately acknowledge Telegram button
    # --------------------------------------------

    ack = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={
            "callback_query_id": callback["id"],
            "text": "Processing..."
        },
        timeout=20
    )

    print(f"Callback acknowledgement: {ack.status_code}")

    try:

        if action == "applied":

            tracker.loc[index, "status"] = "Applied"

            update_listing(url, "Applied")

            log.loc[len(log)] = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                url,
                prop["title"],
                prop["price"],
                "Applied",
                "Completed"
            ]

            finish_message(
                chat,
                msg,
                prop["title"],
                prop["city"],
                "Applied"
            )

            print("Applied processed successfully.")

        elif action == "reject":

            tracker.loc[index, "status"] = "Rejected"

            update_listing(url, "Rejected")

            finish_message(
                chat,
                msg,
                prop["title"],
                prop["city"],
                "Rejected"
            )

            print("Rejected processed successfully.")

        elif action == "save":

            tracker.loc[index, "status"] = "Saved"

            update_listing(url, "Saved")

            finish_message(
                chat,
                msg,
                prop["title"],
                prop["city"],
                "Saved"
            )

            print("Saved processed successfully.")

        else:

            print(f"Unknown action: {action}")

    except Exception as e:

        print(f"ERROR processing callback: {e}")

    processed += 1

# ---------------------------------------------------------
# Save database
# ---------------------------------------------------------

tracker.to_csv(TRACKER, index=False)
log.to_csv(LOG, index=False)

print(f"Processed callbacks: {processed}")

# ---------------------------------------------------------
# Clear processed Telegram updates
# ---------------------------------------------------------

if updates.get("result"):

    last = max(u["update_id"] for u in updates["result"])

    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"offset": last + 1},
        timeout=20
    )

    print(f"Offset advanced to {last+1}")

print("=" * 60)
print("CALLBACK HANDLER FINISHED")
print("=" * 60)
