from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parent
STATUS_FILE = ROOT / "Database/listing_status.json"


def load_status():

    if STATUS_FILE.exists():
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def save_status(data):

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def update_listing(url, status):

    data = load_status()

    data[url] = {
        "status": status,
        "time": datetime.now().isoformat()
    }

    save_status(data)
