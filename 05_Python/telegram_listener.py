from pathlib import Path
import json
import requests
import pandas as pd
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

CONFIG = ROOT/"05_Python/Config/config.json"
TRACKER = ROOT/"05_Python/Database/housing_tracker.csv"
LOG = ROOT/"05_Python/Database/applications_log.csv"

with open(CONFIG,"r",encoding="utf-8") as f:
    config=json.load(f)

TOKEN=config["telegram"]["bot_token"]

tracker=pd.read_csv(TRACKER)
log=pd.read_csv(LOG)

updates=requests.get(
    f"https://api.telegram.org/bot{TOKEN}/getUpdates"
).json()

processed=0

for item in updates.get("result",[]):

    callback=item.get("callback_query")

    if callback is None:
        continue

    action,index=callback["data"].split("|")
    index=int(index)

    prop=tracker.loc[index]

    chat_id=callback["message"]["chat"]["id"]
    message_id=callback["message"]["message_id"]

    if action=="message":

        msg=(
            f"Hello,\\n\\n"
            f"I am interested in {prop['title']}.\\n\\n"
            f"The location in {prop['area'].title()} fits my relocation plans very well.\\n\\n"
            f"I would appreciate the opportunity to arrange a viewing.\\n\\n"
            f"Kind regards,\\n"
            f"Grifton Muchovu"
        )

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":msg}
        )

    elif action=="applied":

        tracker.loc[index,"property_state"]="applied"

        if not (
            (log["url"]==prop["url"]) &
            (log["decision"]=="applied")
        ).any():

            log.loc[len(log)] = [
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                prop["url"],
                prop["title"],
                prop["rent"],
                "applied",
                "completed"
            ]

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/editMessageText",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "text":"🟢 Applied Successfully"
            }
        )

    elif action=="reject":

        tracker.loc[index,"property_state"]="rejected"

        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/editMessageText",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "text":"❌ Property Rejected"
            }
        )

    processed+=1

tracker.to_csv(TRACKER,index=False)
log.to_csv(LOG,index=False)

print(f"Processed {processed} callbacks.")

if updates["result"]:
    last=max(u["update_id"] for u in updates["result"])
    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={"offset":last+1}
    )
