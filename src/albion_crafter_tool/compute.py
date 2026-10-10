import fnmatch
import functools
import math

import aodp_data

focus = False
base_bonus = 18
city_bonus = 0  # 15
daily_bonus = 0  # 10 #20
focus_bonus = 59 if focus else 0
bonus = (base_bonus + city_bonus + daily_bonus + focus_bonus) / 100
rrr = bonus / (1 + bonus)

station_rate = 300


@functools.cache
def compute_quantity_rrr(run, unit_qty):
    base_qty = math.ceil(run * unit_qty * (1 - rrr))
    return base_qty
    base_run = 0
    current_qty = base_qty
    while current_qty > unit_qty:
        nb_run = current_qty // unit_qty
        used_qty = nb_run * unit_qty
        unused_qty = current_qty % unit_qty
        rrr_qty = math.floor(used_qty * rrr)
        current_qty = unused_qty + rrr_qty
        base_run += nb_run
    if base_run == run - 1:
        base_qty += unit_qty - current_qty
        return base_qty + unit_qty - current_qty
    raise Exception("Need to be refactor")


def compute_recipe(recipe, prices, daily_sold):
    # usage fee
    item_xml_id = recipe["item_xml_id"]
    item_value = recipe["item_value"]
    amount_crafted = recipe["amount_crafted"]
    run = (0.2 * daily_sold) // amount_crafted
    # unit_focus = compute_focus(item_xml_id, recipe["craftingfocus"])
    # unit_per_daily_focus = (10_000 // unit_focus) if unit_focus else 0
    nutrition_consumed = item_value * 0.1125 * amount_crafted * run
    usage_fee = nutrition_consumed * station_rate / 100
    # input
    resource_cost = 0
    resource_sell = 0
    for i in recipe["lines"]:
        price = aodp_data.get_price(i["item_xml_id"], prices)
        cost_qty = (
            run * i["count"]
            if i["no_return"] or run == 0
            else compute_quantity_rrr(run, i["count"])
        )
        sell_qty = 0 if i["no_return"] or run == 0 else math.floor(i["count"] * rrr)
        resource_cost += cost_qty * price
        resource_sell += sell_qty * price
        # TODO sell fee here per input
    # output
    output_price = aodp_data.get_price(item_xml_id, prices)
    output_qty = amount_crafted * run
    # summary
    income = resource_sell + output_price * output_qty
    sales_fee = income * (2.5 + 4) / 100
    expence = resource_cost + usage_fee + sales_fee
    profit = income - expence
    roi = profit / expence * 100 if expence != 0 else 0


def compute_focus(item, base_focus):
    # https://albionfreemarket.com/articles/view/how-crafting-specialization-reduces-focus-costs-in-albion-online
    bonus = get_focus_bonus(item)
    focus_cost = base_focus * 0.5 ** (bonus / 10_000)
    return focus_cost


def get_focus_bonus(item):
    total_bonus = 0
    for templateachievement in achievements_root.findall(
        './/templateachievement[@missiontype="craftitemfame"]'
    ):
        for bonus in templateachievement.findall(
            './/bonus[@type="craftingfocuscostreduction"]'
        ):
            for itempattern in bonus.findall(".//itempattern"):
                pattern = itempattern.attrib["pattern"]
                if fnmatch.fnmatch(item, pattern):
                    name = templateachievement.attrib["id"]
                    # description = bonus.find("./description").attrib["tag"]
                    bonus_number = float(bonus.attrib["bonus"]) * 100
                    total_bonus += specs[name] * bonus_number
    return total_bonus
