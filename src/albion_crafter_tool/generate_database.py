from albion_data import con, cur
from lxml import etree


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


def generate_tables():
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
            crafting_category TEXT,
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
    cur.execute("DROP TABLE IF EXISTS location")
    cur.execute(
        """
        CREATE TABLE location(
            id INTEGER PRIMARY KEY,
            xml_id TEXT,
            name TEXT,
            crafting_bonus INTEGER,
            refining_bonus INTEGER
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS location_bonus")
    cur.execute(
        """
        CREATE TABLE location_bonus(
            id INTEGER PRIMARY KEY,
            location_id INTEGER,
            crafting_category TEXT,
            value INTEGER,
            FOREIGN KEY(location_id) REFERENCES location(id)
        )"""
    )
    cur.execute("DROP TABLE IF EXISTS event_bonus")
    cur.execute(
        """
        CREATE TABLE event_bonus(
            id INTEGER PRIMARY KEY,
            xml_id TEXT,
            crafting_category TEXT,
            value INTEGER
        )"""
    )


def _get_xml_data(item, enchantment):
    uniquename = item.attrib["uniquename"]
    craftingcategory = item.attrib.get("craftingcategory")
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
        "craftingcategory": craftingcategory,
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


def generate_items_and_recipes():
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
        "//*[self::trackingitem or self::simpleitem or self::equipmentitem or self::weapon or self::transformationweapon or self::consumableitem]"
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
        "INSERT INTO item(xml_id, name, tier, enchantment_level, item_value, crafting_category, category_id) SELECT ?, ?, ?, ?, ?, ?, id FROM category WHERE path = ?",
        [
            (
                d["xml_id"],
                d["name"],
                d["tier"],
                d["enchantmentlevel"],
                d["itemvalue"],
                d["craftingcategory"],
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


def generate_item_values():
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


def generate_bonuses():
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


def generate_locations():
    print("Location")
    craftingmodifiers_tree = etree.parse("ao-bin-dumps/craftingmodifiers.xml")
    world_tree = etree.parse("ao-bin-dumps/cluster/world_europe.xml")

    for craftinglocation in craftingmodifiers_tree.findall(".//craftinglocation"):
        cluster_id = craftinglocation.attrib.get("clusterid")
        if cluster_id:
            refiningbonus = craftinglocation.find("./refiningbonus")
            refiningbonus = (
                refiningbonus.attrib["value"] if refiningbonus is not None else 0
            )
            craftingbonus = craftinglocation.find("./craftingbonus")
            craftingbonus = (
                craftingbonus.attrib["value"] if craftingbonus is not None else 0
            )
            cluster = world_tree.find(f'.//cluster[@id="{cluster_id}"]')
            name = cluster.attrib["displayname"]
            location_id = cur.execute(
                "INSERT INTO location(xml_id, name, crafting_bonus, refining_bonus) VALUES(?, ?, ?, ?) RETURNING id",
                (cluster_id, name, refiningbonus, craftingbonus),
            ).fetchone()["id"]
            for craftingmodifier in craftinglocation.findall(".//craftingmodifier"):
                cur.execute(
                    "INSERT INTO location_bonus(location_id, crafting_category, value) VALUES(?, ?, ?)",
                    (
                        location_id,
                        craftingmodifier.attrib["name"],
                        craftingmodifier.attrib["value"],
                    ),
                )

    con.commit()


def generate_bonus_events():
    print("Bonus Event")
    festivities_tree = etree.parse("ao-bin-dumps/festivities_europe.xml")

    for craftbonusevent in festivities_tree.findall(".//craftbonusevent"):
        cur.execute(
            "INSERT INTO event_bonus(xml_id, crafting_category, value) VALUES(?, ?, ?)",
            (
                craftbonusevent.attrib["uniquename"],
                craftbonusevent.attrib["category"],
                craftbonusevent.attrib["value"],
            ),
        )

    con.commit()


if __name__ == "__main__":
    generate_tables()
    generate_items_and_recipes()
    generate_bonuses()
    generate_locations()
    generate_bonus_events()
    generate_item_values()
