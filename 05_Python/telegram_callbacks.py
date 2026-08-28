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

tracker = pd.read_csv(TRACKER)

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

updates = requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getUpdates",
    timeout=20
).json()

processed = 0

for item in updates.get("result", []):

    callback = item.get("callback_query")

    if callback is None:
        continue

    data = callback["data"]

    if "_" not in data:
        continue

    action, index = data.split("_", 1)

    try:
        index = int(index)
    except:
        continue

    if index >= len(tracker):
        continue

    prop = tracker.loc[index]

    chat = callback["message"]["chat"]["id"]
    msg = callback["message"]["message_id"]

    url = prop["url"]

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

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={
            "callback_query_id": callback["id"]
        },
        timeout=20
    )

    processed += 1

tracker.to_csv(TRACKER, index=False)
log.to_csv(LOG, index=False)

if updates.get("result"):
    last = max(u["update_id"] for u in updates["result"])
    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"offset": last + 1},
        timeout=20
    )

print(f"Processed {processed} callbacks.")
