import requests
import math

BASE_URL = "https://europe.albion-online-data.com"


# Prices
def get_prices(items, locations="Lymhurst", qualities="1"):
    if not items:
        return []
    res = requests.get(
        BASE_URL + f"/api/v2/stats/prices/{items}.json",
        params={
            "locations": locations,
            "qualities": qualities,
        },
    )
    return res.json()


def get_missing_prices(prices):
    return [(p["item_id"], p["city"]) for p in prices if not p["sell_price_min"]]


def get_price(item, prices, city="Lymhurst", quality=1):
    return next(
        (
            p["sell_price_min"]
            for p in prices
            if p["item_id"] == item and p["city"] == city and p["quality"] == quality
        ),
        0,
    )


# History
def get_price_history(items, cities="Lymhurst", qualities="1"):
    if not items:
        return []
    res = requests.get(
        BASE_URL + f"/api/v2/stats/history/{items}.json",
        params={"locations": cities, "qualities": qualities, "time-scale": "24"},
    )
    return res.json()


def compute_daily_sold(item, price_history, city="Lymhurst", quality=1):
    data = next(
        (
            h["data"]
            for h in price_history
            if h["item_id"] == item
            and h["location"] == city
            and h["quality"] == quality
        ),
        [],
    )
    return sum(d["item_count"] for d in data[-8:-1]) // 7


def get_item_quantity_from_daily_sold(
    item, price_history, percentage, city="Lymhurst", quality=1
):
    return math.floor(
        compute_daily_sold(item, price_history, city, quality) * percentage
    )
