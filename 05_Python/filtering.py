def filter_launch_listings(listings, config):
    """
    Keep only worthwhile listings for launch.
    """

    minimum_score = 70

    listings = [
        x for x in listings
        if x.get("score", 0) >= minimum_score
    ]

    listings.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return listings[:5]
