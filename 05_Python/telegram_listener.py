import requests

BOT_TOKEN="8963641889:AAG15IE0gjF5huojqXffVcToO6_kGoA0RLc"
CHAT_ID="8674673640"

def send_property_alert(p):

    if p["score"]>=90:
        badge="🔥 HIGH PRIORITY"
    elif p["score"]>=70:
        badge="⭐ STRONG MATCH"
    else:
        badge="📍 NEW LISTING"

    msg=f"""
🏠 <b>Housing Agent v5</b>

<b>{badge}</b>

📍 <b>{p['title']}</b>
🏙 {p['city']}

💶 <b>{p['price']}</b>
🛏 {p['rooms']} rooms
📐 {p['area']} m²

🏢 {p.get('agency','')}

🎯 <b>Score: {p['score']}/100</b>

<a href="{p['url']}">🏡 Open Listing</a>
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":CHAT_ID,
            "text":msg,
            "parse_mode":"HTML",
            "disable_web_page_preview":False
        },
        timeout=20
    )
