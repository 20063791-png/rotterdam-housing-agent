CHAT_ID = os.getenv("CHAT_ID") or "8674673640"

# ==========================================================
# FIX: Get correct city from Pararius URL
# Get correct city from Pararius URL
# ==========================================================

def extract_city_from_url(url: str) -> str:
"""
   Extract city from Pararius URLs.

    Examples:
    apartment-for-rent/delft/...      -> Delft
    room-for-rent/schiedam/...        -> Schiedam
    house-for-rent/rotterdam/...      -> Rotterdam
    studio-for-rent/vlaardingen/...   -> Vlaardingen
    apartment-for-rent/delft/...    -> Delft
    room-for-rent/schiedam/...      -> Schiedam
    house-for-rent/rotterdam/...    -> Rotterdam
    studio-for-rent/vlaardingen/... -> Vlaardingen
   """

m = re.search(
@@ -36,8 +35,9 @@ def extract_city_from_url(url: str) -> str:

return "Unknown"


# ==========================================================
# Fast Property Detail Extractor (UNCHANGED)
# Fast Property Detail Extractor
# ==========================================================

async def fetch_listing_details(url):
@@ -153,8 +153,9 @@ async def fetch_listing_details(url):

return details


# ==========================================================
# AI Message Builder (UNCHANGED)
# AI Message Builder
# ==========================================================

def build_ai_message(property_data):
@@ -184,6 +185,7 @@ def build_ai_message(property_data):
Grifton Muchovu
Erasmus MC Researcher"""


# ==========================================================
# Telegram Sender
# ==========================================================
@@ -196,18 +198,14 @@ def send_property_alert(property_data, index=0):

details = asyncio.run(fetch_listing_details(property_data["url"]))

    # ------------------------------------------------------
    # FIX: Always use the city from the URL
    # ------------------------------------------------------
    # Always use city from URL

city = extract_city_from_url(property_data["url"])

    # Copy property data so AI message also gets correct city

property_for_ai = property_data.copy()
property_for_ai["city"] = city

    # Prefer scanner values, fallback to page extraction
    # Prefer scanner values

price = (
f"€{property_data['price']}"
@@ -284,6 +282,10 @@ def send_property_alert(property_data, index=0):

message += f"\n\n🔗 {property_data['url']}"

    # ======================================================
    # UPDATED BUTTONS
    # ======================================================

keyboard = {
"inline_keyboard": [

@@ -307,6 +309,13 @@ def send_property_alert(property_data, index=0):
"text": "🟢 Applied",
"callback_data": f"applied_{index}"
},
                {
                    "text": "📌 Save Later",
                    "callback_data": f"save_{index}"
                }
            ],

            [
{
"text": "❌ Reject",
"callback_data": f"reject_{index}"
@@ -363,6 +372,7 @@ def send_property_alert(property_data, index=0):
else:
print(text_response.text)


# ==========================================================
# Local Test
# ==========================================================
