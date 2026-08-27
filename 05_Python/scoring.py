import re


def extract_price(title):

    m = re.search(r"(\d[\d.,]*)", title.replace(",", ""))

    if not m:
        return None

    try:
        return int(m.group(1).replace(".", ""))
    except:
        return None


def score_listing(city, title, config):

    score = 50

    city_lower = city.lower()
    title_lower = title.lower()

    # ======================================================
    # City Priority
    # ======================================================

    city_bonus = {
        "rotterdam": 30,
        "schiedam": 22,
        "delft": 20,
        "capelle aan den ijssel": 15,
        "vlaardingen": 12,
        "ridderkerk": 8,
        "barendrecht": 8,
        "spijkenisse": 5,
        "dordrecht": 5
    }

    score += city_bonus.get(city_lower, 0)

    # ======================================================
    # Property Type
    # ======================================================

    if "studio" in title_lower:
        score += 15

    elif "apartment" in title_lower:
        score += 12

    elif "flat" in title_lower:
        score += 10

    elif "room" in title_lower:
        score += 6

    # ======================================================
    # Furnishing Bonus
    # ======================================================

    bonuses = [
        "furnished",
        "upholstered",
        "balcony",
        "garden",
        "terrace",
        "parking"
    ]

    for word in bonuses:

        if word in title_lower:
            score += 3

    # ======================================================
    # Price Bonus
    # ======================================================

    price = extract_price(title)

    budget = config["budget"]["three_room"]

    if price:

        if price <= budget * 0.70:
            score += 10

        elif price <= budget:
            score += 6

        elif price <= budget * 1.15:
            score += 2

        else:
            score -= 10

    # ======================================================
    # Registration Preference
    # ======================================================

    if "registration" in title_lower or "inschrijving" in title_lower:
        score += 5

    return max(0, min(score, 100))
