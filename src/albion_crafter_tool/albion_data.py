from __future__ import annotations

import csv
import os
import re
import sqlite3

from lxml import etree


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
LOCATIONS = [L10N_MAPPING[k] for k in L10N_MAPPING if k.startswith("@JOURNAL_CITIES_")]
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


def _get_xml_id(uniquename, enchantmentlevel):
    return f"{uniquename}@{enchantmentlevel}" if enchantmentlevel != "0" else uniquename


def _get_xml_data(item, enchantment):
    uniquename = item.attrib["uniquename"]
    enchantmentlevel = enchantment.attrib.get("enchantmentlevel", "0")
    tier = item.attrib.get("tier")
    itemvalue = enchantment.attrib.get("itemvalue")
    name = get_translation("@ITEMS", uniquename)
    if name and tier:
        name += f" [{tier}.{enchantmentlevel}]"
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
        "xml_id": _get_xml_id(uniquename, enchantmentlevel),
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
                    "uniquename": _get_xml_id(
                        craftresource.attrib["uniquename"],
                        craftresource.attrib.get("enchantmentlevel", "0"),
                    ),
                    "count": craftresource.attrib["count"],
                    "no_return": bool(
                        craftresource.attrib.get("maxreturnamount", "1") == "0"
                    ),
                }
            )
        recipe_data.append(rdata)
    return item_data, recipe_data


def generate_database():
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
            xml_id TEXT UNIQUE,
            item_value REAL,
            category_id INT,
            FOREIGN KEY(category_id) REFERENCES category(id)
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

    # XML Data
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
        item_data.append(idata)
        recipe_data[idata["xml_id"]] = rdata
        for enchantment in item.findall(".//enchantment"):
            idata, rdata = _get_xml_data(item, enchantment)
            item_data.append(idata)
            recipe_data[idata["xml_id"]] = rdata

    # Item SQL
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
    # Recipe SQL
    for item, data_list in recipe_data.items():
        for data in data_list:
            cur.execute(
                """
                INSERT INTO recipe(item_id, amount_crafted, crafting_focus)
                SELECT id, ?, ? FROM item
                WHERE item.xml_id = ?
                RETURNING id
                """,
                (
                    data["amountcrafted"],
                    data["craftingfocus"],
                    item,
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
                    """,
                    (
                        recipe_id,
                        line["count"],
                        line["no_return"],
                        line["uniquename"],
                    ),
                )

    pp = False

    def p(v):
        if pp:
            print(v)

    # Update Item Value
    while True:
        update = False
        items = cur.execute(
            "SELECT id, xml_id from item WHERE item_value IS NULL"
        ).fetchall()
        for item, xml_id in items:
            pp = xml_id == "T2_POTION_ENERGY@1"
            for recipe in cur.execute(
                "SELECT id, amount_crafted FROM recipe WHERE item_id = ?", (item["id"],)
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


if __name__ == "__main__":
    if input("Type 'gen' to regen the database\n>") == "gen":
        generate_database()
    # get_item("T6_POTION_ENERGY")
    # print(get_items_from_category("/consumables/potions/energy"))
    # print(search_category("energy"))
    # print(search_category("Hide"))
