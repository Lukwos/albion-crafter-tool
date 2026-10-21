import functools
import math

import aodp_data
import albion_data


def get_rrr(focus, daily_bonus):
    base_bonus = 18
    city_bonus = 0  # 15
    # daily_bonus = 0  # 10 #20
    focus_bonus = 59 if focus else 0
    bonus = (base_bonus + city_bonus + daily_bonus + focus_bonus) / 100
    rrr = bonus / (1 + bonus)
    return rrr


def compute_recipe(recipe, prices, station_rate, use_focus, have_premium):
    item_xml_id = recipe["item_xml_id"]
    item_value = recipe["item_value"] or 0
    amount_crafted = recipe["amount_crafted"]
    runs = recipe.get("with", {}).get("runs", 0)
    rrr = get_rrr(use_focus, 0)
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


# def get_focus_bonus(item):
#     total_bonus = 0
#     for templateachievement in achievements_root.findall(
#         './/templateachievement[@missiontype="craftitemfame"]'
#     ):
#         for bonus in templateachievement.findall(
#             './/bonus[@type="craftingfocuscostreduction"]'
#         ):
#             for itempattern in bonus.findall(".//itempattern"):
#                 pattern = itempattern.attrib["pattern"]
#                 if fnmatch.fnmatch(item, pattern):
#                     name = templateachievement.attrib["id"]
#                     # description = bonus.find("./description").attrib["tag"]
#                     bonus_number = float(bonus.attrib["bonus"]) * 100
#                     total_bonus += specs[name] * bonus_number
#     return total_bonus
