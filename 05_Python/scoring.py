import re

def extract_price(title):
    m = re.search(r"€?\s?([\d.]+)", title)
    if m:
        return int(m.group(1).replace(".", ""))
    return None


def score_listing(city, title, config):

    score = 50

    city_lower = city.lower()

    if city_lower == "rotterdam":
        score += config["scoring"]["rotterdam_bonus"]

    elif city_lower in ["schiedam", "delft"]:
        score += config["scoring"]["schiedam_bonus"]

    elif city_lower in [
        "capelle aan den ijssel",
        "vlaardingen",
        "barendrecht",
        "ridderkerk"
    ]:
        score += config["scoring"]["nearby_bonus"]

    else:
        score += config["scoring"]["outer_bonus"]

    price = extract_price(title)

    if price:

        if price <= config["budget"]["room"]:
            score += 20

        elif price <= config["budget"]["studio"]:
            score += 15

        elif price <= config["budget"]["two_room"]:
            score += 10

        elif price <= config["budget"]["three_room"]:
            score += 5

        elif price > config["filters"]["absolute_max_price"]:
            score -= 35

    return max(0, min(score, 100))
