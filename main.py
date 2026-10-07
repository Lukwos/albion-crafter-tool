import math
import requests
import xml.etree.ElementTree as ET
import csv
import functools
import fnmatch
import re

# https://albionfreemarket.com/articles/view/how-crafting-station-fees-are-calculated-in-albion-online
# https://www.albioncodex.com/guides/albion-online-return-rate-explained

base_url = "https://europe.albion-online-data.com"
tree = ET.parse("ao-bin-dumps/items.xml")
root = tree.getroot()
achievements_tree = ET.parse("ao-bin-dumps/achievements.xml")
achievements_root = achievements_tree.getroot()

l10n_name_list = {}
with open("data/l10n.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        l10n_name_list[row["id"]] = row["name"]


def b(prefix, id):
    name = l10n_name_list.get(f"{prefix}_{id}")
    if not name:
        return id
    return name


def get_categories():
    # ids = {
    #     el.attrib["id"]
    #     for el in (
    #         root.findall(".//shopcategory")
    #         + root.findall(".//shopsubcategory")
    #         + root.findall(".//shopsubcategory2")
    #         + root.findall(".//shopsubcategory3")
    #     )
    # }
    ids = ["potions", "hide", "leather"]
    data = []
    for id in ids:
        name = b("@MARKETPLACEGUI_ROLLOUT_SHOPSUBCATEGORY", id.upper())
        data.append((name, id))
    return data


categories = get_categories()

specs = {}
with open("data/specs.csv", newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        specs[row["id"]] = int(row["value"])

focus = False
base_bonus = 18
city_bonus = 0  # 15
daily_bonus = 0  # 10 #20
focus_bonus = 59 if focus else 0
bonus = (base_bonus + city_bonus + daily_bonus + focus_bonus) / 100
rrr = bonus / (1 + bonus)

station_rate = 300


def generate_specs_file():
    with open("data/export_specs_afm.txt", newline="") as file:
        export_file = file.read()
    with open("data/specs.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "value"])
        for templateachievement in achievements_root.findall(
            './/templateachievement[@missiontype="craftitemfame"]'
        ):
            id = templateachievement.attrib["id"]
            name = b("@DESTINYBOARD_TITLE", id)
            pattern = rf"{name}: ?(\d+) \/ \d+"
            export_spec = re.findall(
                pattern,
                export_file,
            )
            writer.writerow([id, export_spec[0] if export_spec else 0])


def get_prices(items, cities="Lymhurst", qualities="1"):
    if not items:
        return []
    items = ",".join(items)
    res = requests.get(
        base_url + f"/api/v2/stats/prices/{items}.json",
        params={
            "locations": cities,
            "qualities": qualities,
        },
    )
    return res.json()


def get_recipes(item):
    data = {"name": item, "recipes": []}
    for craftingrequirements in root.findall(
        f'.//*[@uniquename="{item}"]/craftingrequirements'
    ):
        rdata = {
            "amountcrafted": int(craftingrequirements.attrib.get("amountcrafted", "1")),
            "craftingfocus": int(craftingrequirements.attrib.get("craftingfocus", "0")),
            "inputs": [],
        }
        for craftresource in craftingrequirements.findall("./craftresource"):
            rdata["inputs"].append(
                {
                    "uniquename": craftresource.attrib["uniquename"],
                    "count": int(craftresource.attrib["count"]),
                    "no_return": "maxreturnamount" in craftresource.attrib,
                }
            )
        data["recipes"].append(rdata)
    return data


def compute_item_value(item):
    simpleitem = root.find(f'.//simpleitem[@uniquename="{item}"]')
    if simpleitem is not None and "itemvalue" in simpleitem.attrib:
        return float(simpleitem.attrib["itemvalue"])
    else:
        recipes = get_recipes(item)["recipes"]
        item_value = 0
        if recipes:
            amountcrafted = recipes[0]["amountcrafted"]
            for i in recipes[0]["inputs"]:
                item_value += compute_item_value(i["uniquename"]) * i["count"]
            item_value //= amountcrafted
        return item_value


def get_item_list_from_item_data(item_data):
    return {item_data["name"]} | {
        r["uniquename"] for recipe in item_data["recipes"] for r in recipe["inputs"]
    }


def get_price(item, prices, city="Lymhurst", quality=1):
    return next(
        (
            p["sell_price_min"]
            for p in prices
            if p["item_id"] == item and p["city"] == city and p["quality"] == quality
        ),
        0,
    )


def print_recipe_report(report):
    print("=" * 60)
    print("====", b("@ITEMS", report["name"]))
    print("daily_sold", report["daily_sold"])
    print("run", report["run"])
    print("unit_per_daily_focus", report["unit_per_daily_focus"])
    print("rrr", rrr)
    print("station rate", station_rate)
    print("== input")
    for i in report["inputs"]:
        print("-", b("@ITEMS", i["uniquename"]), i["cost_qty"], i["price"])
        print("+", b("@ITEMS", i["uniquename"]), i["sell_qty"], i["price"])
    print("== output")
    print(
        "+", b("@ITEMS", report["name"]), report["output_qty"], report["output_price"]
    )
    print("== summary")
    print("expence", -report["expence"])
    print("income", report["income"])
    print("roi", report["roi"], "%")
    print("resource_cost", report["resource_cost"])
    print("resource_sell", report["resource_sell"])
    print("usage_fee", report["usage_fee"])
    print("sales_fee", report["sales_fee"])
    print("=" * 60)


@functools.cache
def compute_quantity_rrr(run, unit_qty):
    base_qty = math.ceil(run * unit_qty * (1 - rrr))
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
    elif base_run == run:
        return base_qty
    raise Exception("Need to be refactor")


def compute_recipe(item, recipe, prices, daily_sold):
    item_value = compute_item_value(item)
    # usage fee
    run = (0.2 * daily_sold) // recipe["amountcrafted"]
    unit_focus = compute_focus(item, recipe["craftingfocus"])
    unit_per_daily_focus = (10_000 // unit_focus) if unit_focus else 0
    nutrition_consumed = item_value * 0.1125 * recipe["amountcrafted"] * run
    usage_fee = nutrition_consumed * station_rate / 100
    # input
    resource_cost = 0
    resource_sell = 0
    report = {
        "missing_price": False,
        "name": item,
        "daily_sold": daily_sold,
        "run": run,
        "usage_fee": usage_fee,
        "unit_per_daily_focus": unit_per_daily_focus,
        "inputs": [],
    }
    for i in recipe["inputs"]:
        price = get_price(i["uniquename"], prices)
        # cost_qty = (
        #     run * i["count"]
        #     if i["no_return"]
        #     else math.ceil(run * i["count"] * (1 - rrr))
        # )
        cost_qty = (
            run * i["count"]
            if i["no_return"] or run == 0
            else compute_quantity_rrr(run, i["count"])
        )
        sell_qty = 0 if i["no_return"] or run == 0 else math.floor(i["count"] * rrr)
        resource_cost += cost_qty * price
        resource_sell += sell_qty * price
        report["inputs"].append(
            {
                "uniquename": i["uniquename"],
                "cost_qty": cost_qty,
                "sell_qty": sell_qty,
                "price": price,
            }
        )
        if not price:
            report["missing_price"] = True
        # TODO sell fee here per input
    # output
    output_price = get_price(item, prices)
    output_qty = recipe["amountcrafted"] * run
    # summary
    income = resource_sell + output_price * output_qty
    sales_fee = income * (2.5 + 4) / 100
    expence = resource_cost + usage_fee + sales_fee
    profit = income - expence
    roi = profit / expence * 100 if expence != 0 else 0
    report.update(
        {
            "output_price": output_price,
            "output_qty": output_qty,
            "resource_cost": resource_cost,
            "resource_sell": resource_sell,
            "usage_fee": usage_fee,
            "sales_fee": sales_fee,
            "expence": expence,
            "income": income,
            "roi": roi,
            "profit": profit,
        }
    )
    if not output_price:
        report["missing_price"] = True
    return report


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


def get_item_list_from_category(category, tiers=None):
    if tiers is None:
        tiers = [1, 2, 3, 4, 5, 6, 7, 8]
    return {
        element.attrib["uniquename"]
        for element in (
            root.findall(f'.//*[@shopcategory="{category}"]')
            + root.findall(f'.//*[@shopsubcategory1="{category}"]')
            + root.findall(f'.//*[@shopsubcategory2="{category}"]')
            + root.findall(f'.//*[@shopsubcategory3="{category}"]')
        )
        if any(element.attrib["uniquename"].startswith(f"T{t}") for t in tiers)
    }


def get_missing_prices(prices):
    return [(p["item_id"], p["city"]) for p in prices if not p["sell_price_min"]]


def print_missing_prices(missing_prices):
    print("=== Missing Prices")
    for p in missing_prices:
        print(f"{b('@ITEMS', p[0]):<40}{p[1]}")


def print_reports(reports):
    print("=== Reports")
    print(f"{'ID':<40} | {'Name':<40} | {'Run':<10} | {'ROI':<10} | Profit")
    print("—" * (40 + 3 + 40 + 3 + 10 + 3 + 10 + 3 + 10))

    for r in reports:
        if r["missing_price"]:
            continue
        print(
            f"{r['name']:<40} | {b('@ITEMS', r['name']):<40} | {r['run']:>10} | {r['roi']:>10.2f} | {int(r['profit']):>10,}"
        )


def generate_l10n_file():
    l10n_tree = ET.parse("ao-bin-dumps/localization.xml")
    l10n_root = l10n_tree.getroot()
    with open("data/l10n.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "name"])
        for tu in l10n_root.findall(".//body/tu"):
            tuid = tu.attrib["tuid"]
            if not tuid.startswith(
                (
                    "@ITEMS",
                    "@DESTINYBOARD_TITLE",
                    "@MARKETPLACEGUI_ROLLOUT_SHOPSUBCATEGORY",
                )
            ):
                continue
            if len(tu) == 0:
                continue
            name = tu[0][0].text
            writer.writerow([tuid, name])


def get_history(items, cities="Lymhurst", qualities="1"):
    if not items:
        return []
    items = ",".join(items)
    res = requests.get(
        base_url + f"/api/v2/stats/history/{items}.json",
        params={"locations": cities, "qualities": qualities, "time-scale": "24"},
    )
    return res.json()


def compute_daily_sold(item, history, city="Lymhurst", quality=1):
    data = next(
        (
            h["data"]
            for h in history
            if h["item_id"] == item
            and h["location"] == city
            and h["quality"] == quality
        ),
        [],
    )
    return sum(d["item_count"] for d in data[-8:-1]) // 7


def main():
    item_datas = []
    item_list = set()
    for item in get_item_list_from_category("potions"):
        item_data = get_recipes(item)
        item_list |= get_item_list_from_item_data(item_data)
        item_datas.append(item_data)
    prices = get_prices(item_list)
    history = get_history(item_list)
    missing_prices = get_missing_prices(prices)
    if missing_prices:
        print_missing_prices(missing_prices)
    reports = []
    for item_data in item_datas:
        for recipe in item_data["recipes"]:
            daily_sold = compute_daily_sold(item_data["name"], history)
            report = compute_recipe(item_data["name"], recipe, prices, daily_sold)
            reports.append(report)
            if item_data["name"] == "T4_POTION_LAVA":
                print_recipe_report(report)
    reports = sorted(
        filter(lambda r: not r["missing_price"], reports),
        key=lambda r: r["roi"],
        reverse=True,
    )
    print_reports(reports)
    print_recipe_report(reports[0])


if __name__ == "__main__":
    generate_l10n_file()
    generate_specs_file()
    # print(compute_item_value("T6_POTION_COOLDOWN"))
    # compute_quantity_rrr(15, 24)
    # history = get_history(["T5_POTION_MOB_RESET"])
    # print(compute_daily_sold("T5_POTION_MOB_RESET", history))
    # main()
    # print(compute_focus("T4_MAIN_SWORD", 1286))
