from pathlib import Path
import json
import os
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent

CONFIG = ROOT / "Config/config.json"
TRACKER = ROOT / "Database/housing_tracker.csv"

with open(CONFIG, "r", encoding="utf-8") as f:
    cfg = json.load(f)

BOT_TOKEN = os.getenv("BOT_TOKEN") or cfg["telegram"]["bot_token"]
CHAT_ID = os.getenv("CHAT_ID") or cfg["telegram"]["chat_id"]

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

tracker = pd.read_csv(TRACKER)

print("=" * 60)
print("TELEGRAM LISTENER")
print("=" * 60)
print(f"Listings available: {len(tracker)}")

# ------------------------------------------------------------
# Send one property
# ------------------------------------------------------------

def send_property(prop):

    property_id = str(prop["property_id"])

    status = str(prop.get("status", "new")).lower()

    if status in ["applied", "rejected"]:
        print(f"Skipping completed listing: {property_id}")
        return False

    score = int(prop.get("score", 0))

    if score >= 80:
        badge = "🔥 PERFECT MATCH"
    elif score >= 70:
        badge = "✨ STRONG MATCH"
    elif score >= 60:
        badge = "👍 GOOD MATCH"
    else:
        badge = "🏠 NEW LISTING"

    message = f"""{badge}

📍 {prop.get("address","")}
🏙 {prop.get("city","")}
💶 €{prop.get("price","")}
🛏 {prop.get("rooms","")} room
📐 {prop.get("area","")} m²

🎯 Score: {score}/100

🔗 {prop.get("listing_url","")}
"""

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🏡 Open Listing",
                    "url": prop.get("listing_url","")
                }
            ],
            [
                {
                    "text": "📋 Copy All Message",
                    "switch_inline_query_current_chat": message
                }
            ],
            [
                {
                    "text": "🟢 Applied",
                    "callback_data": f"applied|{property_id}"
                },
                {
                    "text": "📌 Save Later",
                    "callback_data": f"save|{property_id}"
                }
            ],
            [
                {
                    "text": "❌ Reject",
                    "callback_data": f"reject|{property_id}"
                }
            ]
        ]
    }

    photo = str(prop.get("photo_url","")).strip()

    print("-" * 50)
    print(f"Sending property: {property_id}")
    print(f"Photo exists: {bool(photo)}")

    # --------------------------------------------------------
    # Try sending photo first
    # --------------------------------------------------------

    if photo and photo.lower() != "nan":

        response = requests.post(
            f"{API}/sendPhoto",
            json={
                "chat_id": CHAT_ID,
                "photo": photo,
                "caption": message,
                "reply_markup": keyboard
            },
            timeout=30
        )

        print(f"sendPhoto HTTP: {response.status_code}")

        try:
            print(response.json())
        except:
            print(response.text)

        if response.ok:
            return True

        print("Photo failed. Falling back to text...")

    # --------------------------------------------------------
    # Fallback text message
    # --------------------------------------------------------

    response = requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "reply_markup": keyboard,
            "disable_web_page_preview": False
        },
        timeout=30
    )

    print(f"sendMessage HTTP: {response.status_code}")

    try:
        print(response.json())
    except:
        print(response.text)

    return response.ok

# ------------------------------------------------------------
# Send new listings
# ------------------------------------------------------------

sent = 0

new_rows = tracker[tracker["status"].fillna("new").eq("new")]

print(f"Listings to send: {len(new_rows)}")

for _, prop in new_rows.iterrows():

    if send_property(prop):
        tracker.loc[prop.name, "status"] = "sent"
        sent += 1

tracker.to_csv(TRACKER, index=False)

print("-" * 50)
print(f"Successfully sent: {sent}")
print("=" * 60)
