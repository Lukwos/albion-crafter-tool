from __future__ import annotations

import csv
import os
import re
import sqlite3
import fnmatch

from lxml import etree
import math


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


con = sqlite3.connect("data/data.db")
con.row_factory = dict_factory
cur = con.cursor()


# L10n
def init_translation(lang="EN-US"):
    localization_tree = etree.parse("ao-bin-dumps/localization.xml")
    segs = localization_tree.xpath(f'//tuv[@xml:lang="{lang}"]/seg')
    mapping = {}
    for seg in segs:
        tu = seg.getparent().getparent()
        mapping[tu.attrib["tuid"]] = seg.text
    return mapping


L10N_MAPPING = init_translation()


def get_translation(prefix, value):
    key = f"{prefix}_{value.upper()}"
    name = L10N_MAPPING.get(key, None)
    return name


# Misc
LOCATIONS = [
    # "Arthur's Rest",
    "Brecilien",
    "Bridgewatch",
    "Caerleon",
    "Fort Sterling",
    "Lymhurst",
    "Martlock",
    # "Merlyn's Rest",
    # "Morgana's Rest",
    "Thetford",
    "Black Market",
]
TIERS = [("I", 1), ("II", 2), ("III", 3), ("IV", 4), ("V", 5), ("VI", 6), ("VII", 7), ("VIII", 8)]  # fmt: skip
# Specs
SPECS = {}
if os.path.exists("data/specs.csv"):
    with open("data/specs.csv", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            SPECS[row["id"]] = int(row["value"])


def generate_specs_file():
    achievements_tree = etree.parse("ao-bin-dumps/achievements.xml")
    achievements_root = achievements_tree.getroot()

    with open("data/export_specs_afm.txt", newline="") as file:
        export_file = file.read()
    with open("data/specs.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "value"])
        for templateachievement in achievements_root.findall(
            './/templateachievement[@missiontype="craftitemfame"]'
        ):
            achievement_id = templateachievement.attrib["id"]
            name = get_translation("@DESTINYBOARD_TITLE", achievement_id)
            pattern = rf"{name}: ?(\d+) \/ \d+"
            export_spec = re.findall(
                pattern,
                export_file,
            )
            writer.writerow([achievement_id, export_spec[0] if export_spec else 0])


# Database
def get_item(xml_id):
    item = cur.execute(
        "SELECT * FROM item WHERE xml_id = ? LIMIT 1", (xml_id,)
    ).fetchone()
    return item


def get_items_from_category(category_path):
    items = cur.execute(
        "SELECT i.* FROM item i JOIN category c ON c.id = i.category_id WHERE c.path like ?",
        (f"{category_path}%",),
    ).fetchall()
    return items


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


def get_categories(parent_id=None):
    categories = cur.execute(
        "SELECT * FROM category WHERE parent_id is ?",
        (parent_id,),
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


def _get_xml_data(item, enchantment):
    uniquename = item.attrib["uniquename"]
    enchantmentlevel = enchantment.attrib.get("enchantmentlevel", "0")
    tier = item.attrib.get("tier")
    itemvalue = enchantment.attrib.get("itemvalue")
    name = get_translation("@ITEMS", uniquename)
    if name and tier:
        # name = (
        #     f"[{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}][[/{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}][{TIER_COLOR_MAPPING[tier]}]■[/{TIER_COLOR_MAPPING[tier]}][{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}]][/{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}] "
        #     + name
        # )
        name += f" [{tier}.{enchantmentlevel}]"
        # name += f" [{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}][[/{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}][{TIER_COLOR_MAPPING[tier]}]{tier}.{enchantmentlevel}[/{TIER_COLOR_MAPPING[tier]}][{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}]][/{ENCHANTMENT_COLOR_MAPPING[enchantmentlevel]}]"
    categories = [
        item.attrib.get(c)
        for c in [
            "shopcategory",
            "shopsubcategory1",
            "shopsubcategory2",
            "shopsubcategory3",
        ]
    ]
    path = "/" + "/".join(c for c in categories if c is not None)
    item_data = {
        "xml_id": uniquename,
        "name": name,
        "tier": tier,
        "enchantmentlevel": enchantmentlevel,
        "itemvalue": itemvalue,
        "path": path,
    }
    recipe_data = []
    for craftingrequirements in enchantment.findall("./craftingrequirements"):
        rdata = {
            "amountcrafted": craftingrequirements.attrib.get("amountcrafted", "1"),
            "craftingfocus": craftingrequirements.attrib.get("craftingfocus", "0"),
            "lines": [],
        }
        for craftresource in craftingrequirements.findall("./craftresource"):
            rdata["lines"].append(
                {
                    "uniquename": craftresource.attrib["uniquename"],
                    "enchantmentlevel": craftresource.attrib.get(
                        "enchantmentlevel", "0"
                    ),
                    "count": craftresource.attrib["count"],
                    "no_return": bool(
                        craftresource.attrib.get("maxreturnamount", "1") == "0"
                    ),
                }
            )
        recipe_data.append(rdata)
    return item_data, recipe_data


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
    return math.floor(
        amount_crafted * focus_quantity / compute_focus(item_xml_id, base_focus)
    )


def import_afm_specs(text):
    update = 0
    pattern = r" *(.*): (\d+) \/ \d+"
    cur.execute("UPDATE spec SET value = 0")
    for name, value in re.findall(pattern, text):
        cur.execute("UPDATE spec SET value = ? WHERE name = ?", (value, name))
        update += 1
    con.commit()
    return update


def generate_database():
    print("Create Tables")
    cur.execute("DROP TABLE IF EXISTS category")
    cur.execute(
        """CREATE TABLE category(
            id INTEGER PRIMARY KEY,
            xml_id TEXT,
            name TEXT,
            path TEXT UNIQUE,
            parent_id INT,
            FOREIGN KEY(parent_id) REFERENCES category(id)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS item")
    cur.execute(
        """CREATE TABLE item(
            id INTEGER PRIMARY KEY,
            name TEXT,
            tier INT,
            enchantment_level INT,
            xml_id TEXT,
            item_value REAL,
            category_id INT,
            FOREIGN KEY(category_id) REFERENCES category(id),
            UNIQUE(xml_id, enchantment_level)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS recipe")
    cur.execute(
        """
        CREATE TABLE recipe(
            id INTEGER PRIMARY KEY,
            item_id INTEGER,
            amount_crafted INTEGER,
            crafting_focus REAL,
            FOREIGN KEY(item_id) REFERENCES item(id)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS recipe_line")
    cur.execute(
        """
        CREATE TABLE recipe_line(
            id INTEGER PRIMARY KEY,
            recipe_id INTEGER,
            item_id INTEGER,
            count INTEGER,
            no_return BOOLEAN,
            FOREIGN KEY(recipe_id) REFERENCES recipe(id),
            FOREIGN KEY(item_id) REFERENCES item(id)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS spec")
    cur.execute(
        """
        CREATE TABLE spec(
            id INTEGER PRIMARY KEY,
            xml_id TEXT,
            name TEXT,
            value INTEGER DEFAULT 0
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS bonus")
    cur.execute(
        """
        CREATE TABLE bonus(
            id INTEGER PRIMARY KEY,
            spec_id INTEGER,
            bonus INTEGER,
            min_tier INTEGER,
            max_tier INTEGER,
            FOREIGN KEY(spec_id) REFERENCES spec(id)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS bonus_pattern")
    cur.execute(
        """
        CREATE TABLE bonus_pattern(
            id INTEGER PRIMARY KEY,
            bonus_id INTEGER,
            pattern TEXT,
            FOREIGN KEY(bonus_id) REFERENCES bonus(id)
        )"""
    )

    # XML Data
    print("Get Data")
    items_tree = etree.parse("ao-bin-dumps/items.xml")

    def generate_category(category, parent_id=None, parent_path="/"):
        category_xml_id = category.attrib["id"]
        category_name = get_translation(
            "@MARKETPLACEGUI_ROLLOUT_SHOPSUBCATEGORY", category_xml_id
        ) or get_translation("@MARKETPLACEGUI_ROLLOUT_SHOPCATEGORY", category_xml_id)
        category_path = parent_path + category_xml_id
        category_id = cur.execute(
            "INSERT INTO category(xml_id, name, path, parent_id) VALUES(?, ?, ?, ?) RETURNING id",
            (category_xml_id, category_name, category_path, parent_id),
        ).fetchone()["id"]
        for subcategory in category:
            generate_category(subcategory, category_id, category_path + "/")

    for category in items_tree.find(".//shopcategories"):
        generate_category(category)

    # Items Data
    item_data = []
    recipe_data = {}
    for item in items_tree.xpath(
        "//*[self::trackingitem or self::simpleitem or self::equipmentitem or self::weapon or self::consumableitem]"
    ):
        idata, rdata = _get_xml_data(item, item)
        idata_key = (idata["xml_id"], idata["enchantmentlevel"])
        item_data.append(idata)
        recipe_data[idata_key] = rdata
        for enchantment in item.findall(".//enchantment"):
            idata, rdata = _get_xml_data(item, enchantment)
            idata_key = (idata["xml_id"], idata["enchantmentlevel"])
            item_data.append(idata)
            recipe_data[idata_key] = rdata

    # Item SQL
    print("Items")
    cur.executemany(
        "INSERT INTO item(xml_id, name, tier, enchantment_level, item_value, category_id) SELECT ?, ?, ?, ?, ?, id FROM category WHERE path = ?",
        [
            (
                d["xml_id"],
                d["name"],
                d["tier"],
                d["enchantmentlevel"],
                d["itemvalue"],
                d["path"],
            )
            for d in item_data
        ],
    )
    con.commit()
    print("Recipes")
    # Recipe SQL
    for (item, enchantmentlevel), data_list in recipe_data.items():
        for data in data_list:
            cur.execute(
                """
                INSERT INTO recipe(item_id, amount_crafted, crafting_focus)
                SELECT id, ?, ? FROM item
                WHERE item.xml_id = ?
                AND item.enchantment_level = ?
                RETURNING id
                """,
                (
                    data["amountcrafted"],
                    data["craftingfocus"],
                    item,
                    enchantmentlevel,
                ),
            )
            recipe_id = cur.fetchone()["id"]

            # Recipe Line SQL
            for line in data["lines"]:
                cur.execute(
                    """
                    INSERT INTO recipe_line(recipe_id, item_id, count, no_return)
                    SELECT ?, id, ?, ? FROM item
                    WHERE item.xml_id = ?
                    AND item.enchantment_level = ?
                    """,
                    (
                        recipe_id,
                        line["count"],
                        line["no_return"],
                        line["uniquename"],
                        line["enchantmentlevel"],
                    ),
                )

    print("Item Value")
    # Update Item Value
    cur.execute(
        "UPDATE item SET item_value = 0 WHERE item_value IS NULL AND id NOT IN (SELECT item_id FROM recipe r)"
    )
    while True:
        update = False
        items = cur.execute(
            "SELECT id, xml_id from item WHERE item_value IS NULL"
        ).fetchall()
        print(len(items))
        for item in items:
            item_id = item["id"]
            xml_id = item["xml_id"]
            for recipe in cur.execute(
                "SELECT id, amount_crafted FROM recipe WHERE item_id = ?", (item_id,)
            ).fetchall():
                lines = cur.execute(
                    """
                    SELECT rl.count, i.item_value
                    FROM recipe_line rl
                    JOIN item i ON rl.item_id = i.id
                    WHERE rl.recipe_id = ?
                    """,
                    (recipe["id"],),
                ).fetchall()
                if any(l["item_value"] is None for l in lines):
                    continue
                item_value = (
                    sum(l["count"] * l["item_value"] for l in lines)
                    / recipe["amount_crafted"]
                )
                cur.execute(
                    "UPDATE item SET item_value = ? WHERE id = ?",
                    (item_value, item["id"]),
                )
                update = True
        if not update:
            break

    con.commit()

    print("Bonus")
    achievements_tree = etree.parse("ao-bin-dumps/achievements.xml")

    for templateachievement in achievements_tree.findall(
        './/templateachievement[@missiontype="craftitemfame"]'
    ):
        xml_id = templateachievement.attrib["id"]
        spec_id = cur.execute(
            "INSERT INTO spec(xml_id, name) VALUES(?, ?) RETURNING id",
            (
                xml_id,
                get_translation("@DESTINYBOARD_TITLE", xml_id),
            ),
        ).fetchone()["id"]
        for bonus in templateachievement.findall(
            './/bonus[@type="craftingfocuscostreduction"]'
        ):
            bonus_id = cur.execute(
                "INSERT INTO bonus(spec_id, bonus, min_tier, max_tier) VALUES(?, ?, ?, ?) RETURNING id",
                (
                    spec_id,
                    float(bonus.attrib["bonus"]) * 100,
                    bonus.attrib["mintier"],
                    bonus.attrib["maxtier"],
                ),
            ).fetchone()["id"]
            for itempattern in bonus.findall(".//itempattern"):
                cur.execute(
                    "INSERT INTO bonus_pattern(bonus_id, pattern) VALUES(?, ?)",
                    (bonus_id, itempattern.attrib["pattern"]),
                )

    con.commit()


if __name__ == "__main__":
    if input("Type 'gen' to regen the database\n>") == "gen":
        generate_database()
    # get_item("T6_POTION_ENERGY")
    # print(get_items_from_category("/consumables/potions/energy"))
    # print(search_category("energy"))
    # print(search_category("Hide"))
    # get_focus_bonus("T6_POTION_ENERGY")
    # print(compute_focus("T4_MAIN_SWORD", 1286))
    # print(get_item_quantity_from_focus("T4_MAIN_SWORD", 1, 1286, 9000))
