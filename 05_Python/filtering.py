def filter_launch_listings(listings):

    # Keep only worthwhile listings

    listings = [
        x for x in listings
        if x["score"] >= 70
    ]

    listings.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return listings[:5]
