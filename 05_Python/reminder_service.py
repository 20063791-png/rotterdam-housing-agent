from pathlib import Path
import json
import requests
import os
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent

CONFIG = ROOT / "Config/config.json"
STATUS = ROOT / "Database/listing_status.json"

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]
CHAT = os.getenv("CHAT_ID") or cfg["telegram"]["chat_id"]

if not STATUS.exists():
    exit()

with open(STATUS, "r", encoding="utf-8") as f:
    listings = json.load(f)

changed = False

for url, data in listings.items():

    if data["status"] != "Saved":
        continue

    saved = datetime.fromisoformat(data["time"])
    age = datetime.now() - saved

    if age >= timedelta(hours=72):

        data["status"] = "Expired"
        changed = True
        continue

    remaining = 3 - age.days

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": CHAT,
            "text":
            f"📌 Reminder\n\n{url}\n\n{remaining} day(s) remaining before expiry."
        },
        timeout=20
    )

if changed:
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2)

print("Reminder run completed.")
