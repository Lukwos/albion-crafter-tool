import fnmatch
import math
import re
import sqlite3


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


con = sqlite3.connect("data.db")
con.row_factory = dict_factory
cur = con.cursor()

LOCATIONS = [
    "Brecilien",
    "Bridgewatch",
    "Caerleon",
    "Fort Sterling",
    "Lymhurst",
    "Martlock",
    "Thetford",
    "Black Market",
]

TIERS = [("I", 1), ("II", 2), ("III", 3), ("IV", 4), ("V", 5), ("VI", 6), ("VII", 7), ("VIII", 8)]  # fmt: skip

TIER_COLOR_MAPPING = {
    "1": "#808080",
    "2": "#8B5A2B",
    "3": "#557A46",
    "4": "#3652AD",
    "5": "#B31312",
    "6": "#E57C23",
    "7": "#F4CE14",
    "8": "#E6FFFD",
}

ENCHANTMENT_COLOR_MAPPING = {
    "0": "#808080",
    "1": "#00FF7F",
    "2": "#00F5FF",
    "3": "#A020F0",
    "4": "#FFD700",
}


def get_item(xml_id):
    item = cur.execute(
        "SELECT * FROM item WHERE xml_id = ? LIMIT 1", (xml_id,)
    ).fetchone()
    return item


def get_recipes_from_category(category_path):
    recipes = cur.execute(
        """
        SELECT i.name as item_name, i.xml_id as item_xml_id, i.item_value as item_value, r.*
        FROM item i
        JOIN category c ON c.id = i.category_id
        JOIN recipe r ON r.item_id = i.id
        WHERE c.path like ?
        """,
        (f"{category_path}%",),
    ).fetchall()
    return recipes


def search_category(value):
    categories = cur.execute(
        "SELECT * FROM category WHERE name like ?",
        (f"%{value}%",),
    ).fetchall()
    return categories


def get_recipe_lines(recipe_id):
    recipe_lines = cur.execute(
        """
        SELECT i.name as item_name, i.xml_id as item_xml_id, rl.*
        FROM recipe_line rl
        JOIN item i ON i.id = rl.item_id
        WHERE recipe_id = ?
        """,
        (recipe_id,),
    ).fetchall()
    return recipe_lines


def compute_all_recipes_from_categories(categories):
    all_recipes = []
    all_recipe_id = []
    for category in categories:
        recipes = get_recipes_from_category(category)
        for recipe in recipes:
            if not recipe["id"] in all_recipe_id:
                recipe["lines"] = get_recipe_lines(recipe["id"])
                all_recipes.append(recipe)
                all_recipe_id.append(recipe["id"])

    all_items = [
        {"id": i[0], "xml_id": i[1]}
        for i in {(r["item_id"], r["item_xml_id"]) for r in all_recipes}
        | {(l["item_id"], l["item_xml_id"]) for r in all_recipes for l in r["lines"]}
    ]
    return all_recipes, all_items


def get_focus_bonus(item_xml_id):
    bonus_ids = set()
    for bonus_pattern in cur.execute("SELECT * FROM bonus_pattern").fetchall():
        pattern = bonus_pattern["pattern"]
        if fnmatch.fnmatch(item_xml_id, pattern):
            bonus_ids.add(bonus_pattern["bonus_id"])
    total_bonus = sum(
        res["value"]
        for res in cur.execute(
            f"SELECT s.value * b.bonus AS value FROM bonus b JOIN spec s ON s.id = b.spec_id WHERE b.id IN ({','.join('?' for _ in bonus_ids)})",
            tuple(bonus_ids),
        ).fetchall()
    )
    return total_bonus


def compute_focus(item_xml_id, base_focus):
    # https://albionfreemarket.com/articles/view/how-crafting-specialization-reduces-focus-costs-in-albion-online
    bonus = get_focus_bonus(item_xml_id)
    focus_cost = base_focus * 0.5 ** (bonus / 10_000)
    return focus_cost


def get_item_quantity_from_focus(
    item_xml_id, amount_crafted, base_focus, focus_quantity
):
    unit_focus = compute_focus(item_xml_id, base_focus)
    return math.floor(amount_crafted * focus_quantity / unit_focus) if unit_focus else 0


def import_afm_specs(text):
    update = 0
    pattern = r" *(.*): (\d+) \/ \d+"
    cur.execute("UPDATE spec SET value = 0")
    for name, value in re.findall(pattern, text):
        cur.execute("UPDATE spec SET value = ? WHERE name = ?", (value, name))
        update += 1
    con.commit()
    return update


def get_event_bonuses(xml_ids):
    res = cur.execute(
        f"SELECT b.*,c.name FROM event_bonus b JOIN category c ON c.xml_id = b.crafting_category WHERE b.xml_id IN ({','.join('?' for _ in xml_ids)}) GROUP BY b.crafting_category",
        tuple(xml_ids),
    ).fetchall()
    return res


def get_location_bonuses(location_id):
    location = cur.execute(
        "SELECT * FROM location WHERE xml_id = ?", (location_id,)
    ).fetchone()
    location_bonuses = cur.execute(
        "SELECT b.*,c.name FROM location_bonus b JOIN category c ON c.xml_id = b.crafting_category WHERE location_id = ? GROUP BY b.crafting_category",
        (location["id"],),
    ).fetchall()
    return location, location_bonuses


def get_locations(tnl=False):
    sql = (
        "SELECT * FROM location"
        if tnl
        else "SELECT * FROM location WHERE xml_id not like 'TNL-%'"
    )
    return cur.execute(sql).fetchall()
