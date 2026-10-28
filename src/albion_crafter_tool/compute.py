import functools
import math

from albion_crafter_tool import albion_data, aodp_data


def get_bonuses(location_id):
    # Event
    bonuses = []
    for event in albion_data.get_event_bonuses(
        [e["UniqueName"] for e in aodp_data.get_daily_events()["Events"]]
    ):
        bonuses.append({"name": event["name"], "value": event["value"]})
    location, location_bonuses = albion_data.get_location_bonuses(location_id)
    bonuses.append({"name": "Crafting", "value": location["crafting_bonus"]})
    bonuses.append({"name": "Refining", "value": location["refining_bonus"]})
    for location_bonus in location_bonuses:
        bonuses.append(
            {"name": location_bonus["name"], "value": location_bonus["value"]}
        )
    return bonuses


def get_rrr(crafting_category, use_focus):
    base_bonus = 0.18
    city_bonus = 0  # 0.15
    daily_bonus = 0  # 0.10 #0.20
    for event in albion_data.get_event_bonuses(
        [e["UniqueName"] for e in aodp_data.get_daily_events()["Events"]]
    ):
        if crafting_category == event["crafting_category"]:
            daily_bonus = event["value"]
    focus_bonus = 0.59 if use_focus else 0
    bonus = base_bonus + city_bonus + daily_bonus + focus_bonus
    rrr = bonus / (1 + bonus)
    return rrr


def compute_recipe(recipe, prices, station_rate, use_focus, have_premium):
    item_xml_id = recipe["item_xml_id"]
    crafting_category = recipe["crafting_category"]
    item_value = recipe["item_value"] or 0
    amount_crafted = recipe["amount_crafted"]
    runs = recipe.get("with", {}).get("runs", 0)
    rrr = get_rrr(crafting_category, use_focus)
    recipe.get("with", {})["rrr"] = rrr
    # unit_focus = compute_focus(item_xml_id, recipe["craftingfocus"])
    # unit_per_daily_focus = (10_000 // unit_focus) if unit_focus else 0
    nutrition_consumed = item_value * 0.1125 * amount_crafted * runs
    usage_fee = nutrition_consumed * station_rate / 100
    missing_prices = False
    # input
    resource_cost = 0
    resource_sell = 0
    total_sales_fee = 0
    result = {"inputs": [], "outputs": [], "extras": [], "misc": []}
    for i in recipe["lines"]:
        price = aodp_data.get_price(i["item_xml_id"], prices)
        if price == 0:
            missing_prices = True
        cost_qty = (
            runs * i["count"]
            if i["no_return"] or runs == 0
            else get_min_quantity(runs, i["count"], rrr)
        )
        sell_qty = 0 if i["no_return"] or runs == 0 else math.floor(i["count"] * rrr)
        sell_setup_fee = math.ceil(sell_qty * price * 0.025)
        sell_sales_tax = math.ceil(sell_qty * price * 0.04)
        result["inputs"].append(
            {
                "name": i["item_name"],
                "quantity": cost_qty,
                "price": price,
                "total": cost_qty * price,
                "setup_fee": 0,
                "sales_tax": 0,
            }
        )
        result["extras"].append(
            {
                "name": i["item_name"],
                "quantity": sell_qty,
                "price": price,
                "total": sell_qty * price,
                "setup_fee": sell_setup_fee,
                "sales_tax": sell_sales_tax,
            }
        )
        resource_cost += cost_qty * price
        resource_sell += sell_qty * price
        total_sales_fee += sell_setup_fee
        total_sales_fee += sell_sales_tax
    # output
    output_price = aodp_data.get_price(item_xml_id, prices)
    if output_price == 0:
        missing_prices = True
    output_qty = amount_crafted * runs
    output_setup_fee = math.ceil(output_qty * output_price * 0.025)
    output_sales_tax = math.ceil(
        output_qty * output_price * (0.04 if have_premium else 0.08)
    )
    result["outputs"].append(
        {
            "name": recipe["item_name"],
            "quantity": output_qty,
            "price": output_price,
            "total": output_qty * output_price,
            "setup_fee": math.ceil(output_qty * output_price * 0.025),
            "sales_tax": math.ceil(
                output_qty * output_price * (0.04 if have_premium else 0.08)
            ),
        }
    )
    total_sales_fee += output_setup_fee
    total_sales_fee += output_sales_tax
    # summary
    income = resource_sell + output_price * output_qty
    expence = resource_cost + usage_fee + total_sales_fee
    profit = income - expence
    roi = profit / expence * 100 if expence != 0 else 0
    result["misc"] = {
        "income": income,
        "sales_fee": total_sales_fee,
        "expence": expence,
        "profit": profit,
        "roi": roi,
        "missing_prices": missing_prices,
        "usage_fee": usage_fee,
    }
    return result


@functools.cache
def get_min_quantity(target_run, recipe_qty, rrr):
    min_qty = math.floor(target_run * recipe_qty * (1 - rrr))
    max_qty = target_run * recipe_qty
    for check_qty in range(min_qty, max_qty + 1):
        all_run = 0
        qty = check_qty
        while qty >= recipe_qty:
            run = qty // recipe_qty
            used_qty = run * recipe_qty
            ret_qty = math.floor(used_qty * rrr)
            qty = qty - used_qty + ret_qty
            all_run += run
        if all_run == target_run:
            return check_qty
    raise Exception("Error in RRR computation")


def compute_focus(item, base_focus):
    # https://albionfreemarket.com/articles/view/how-crafting-specialization-reduces-focus-costs-in-albion-online
    bonus = get_focus_bonus(item)
    focus_cost = base_focus * 0.5 ** (bonus / 10_000)
    return focus_cost


if __name__ == "__main__":
    # setup
    location = "Lymhurst"
    use_focus = False
    focus_quantity = 10_000
    daily_sold_percentage = 0.2
    have_premium = True
    station_rate = 300

    # category => recipes + items used
    all_recipes, all_items = albion_data.compute_all_recipes_from_categories(
        ["/consumables/potions/energy"]
    )
    print(all_recipes[0])

    # data from aodp (current prices, history)
    prices = aodp_data.get_prices(
        ",".join(i["xml_id"] for i in all_items),
        locations=location,
    )
    price_history = aodp_data.get_price_history(
        ",".join(i["xml_id"] for i in all_items), cities=location
    )

    # missing prices (output)
    missing_prices = aodp_data.get_missing_prices(prices)
    print(missing_prices)

    # computation
    # per recipe
    recipe = all_recipes[0]
    rrr = get_rrr(recipe["crafting_category"], use_focus)

    # runs
    focus_item_qty = albion_data.get_item_quantity_from_focus(
        recipe["item_xml_id"],
        recipe["amount_crafted"],
        recipe["crafting_focus"],
        focus_quantity,
    )
    daily_sold = aodp_data.compute_daily_sold(
        recipe["item_xml_id"],
        price_history,
        city="Lymhurst",
    )
    runs = min(
        math.floor((daily_sold * (daily_sold_percentage)) // recipe["amount_crafted"]),
        focus_item_qty // recipe["amount_crafted"],
    )
    print(focus_item_qty, daily_sold, runs)

    print(compute_recipe(recipe, prices, station_rate, use_focus, have_premium))
