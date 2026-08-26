from pathlib import Path
import json
import requests
import pandas as pd
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

CONFIG = ROOT/"05_Python/Config/config.json"
TRACKER = ROOT/"05_Python/Database/housing_tracker.csv"

LOG_DIR = ROOT/"05_Python/Logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR/"housing_agent.log"

with open(CONFIG,"r",encoding="utf-8") as f:
    config = json.load(f)

TOKEN = config["telegram"]["bot_token"]
CHAT_ID = config["telegram"]["chat_id"]

def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    with open(LOG_FILE,"a",encoding="utf-8") as f:
        f.write(line+"\\n")

def send_new_property():
    tracker = pd.read_csv(TRACKER)

    if "property_state" not in tracker.columns:
        tracker["property_state"]="new"

    candidates = tracker[
        tracker["property_state"]=="new"
    ].sort_values("opportunity_score",ascending=False)

    if len(candidates)==0:
        log("No new properties.")
        return

    prop = candidates.iloc[0]
    idx = prop.name

    text = (
        "🏠 *Housing Agent v3.0*\\n\\n"
        "⭐ *New Match Found*\\n\\n"
        f"📍 {prop['title']}\\n\\n"
        f"💰 €{int(prop['rent'])}\\n"
        f"🛏 {int(prop['rooms'])} rooms\\n"
        f"📐 {int(prop['sqm'])} m²\\n\\n"
        f"🎯 *Score: {int(prop['opportunity_score'])}/100*"
    )

    keyboard = {
        "inline_keyboard":[
            [{"text":"🏠 Open Listing","url":prop["url"]}],
            [{"text":"📝 AI Message","callback_data":f"message|{idx}"}],
            [
                {"text":"✅ Applied","callback_data":f"applied|{idx}"},
                {"text":"❌ Reject","callback_data":f"reject|{idx}"}
            ]
        ]
    }

    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id":CHAT_ID,
            "text":text,
            "parse_mode":"Markdown",
            "reply_markup":keyboard
        }
    )

    if r.ok:
        tracker.loc[idx,"property_state"]="notified"
        tracker.to_csv(TRACKER,index=False)
        log(f"Sent: {prop['title']}")
    else:
        log(r.text)

def main():
    log("="*50)
    log("Housing Agent Started")
    send_new_property()
    log("Run Complete")

if __name__=="__main__":
    main()
