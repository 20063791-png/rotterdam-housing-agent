import re


def extract_price(title):

    m = re.search(r"€?\s?([\d.]+)", title)

    if m:
        return int(m.group(1).replace(".", ""))

    return None


def filter_launch_listings(listings, config):

    filtered = []

    max_price = config["filters"]["absolute_max_price"]

    for listing in listings:

        price = extract_price(listing["title"])

        if price and price > max_price:
            continue

        filtered.append(listing)

    filtered.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return filtered[:5]
