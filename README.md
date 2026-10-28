albion_data => get info via db
aodp_data => get info via aodp api endpoints
compute => centralization of computation between albion_data, aodp_data and complex calculation
app => just used for textual purposes, update etc

Central point recipe + params + computation results

# Recipe
```python
{
    {
        "item_name": "Minor Energy Potion [2.0]",
        "item_xml_id": "T2_POTION_ENERGY",
        "item_value": 64.0,
        "crafting_category": "potion",
        "id": 272,
        "item_id": 350,
        "amount_crafted": 5,
        "crafting_focus": 56.0,
        "lines": [
            {
                "item_name": "Arcane Agaric [2.0]",
                "item_xml_id": "T2_AGARIC",
                "id": 301,
                "recipe_id": 272,
                "item_id": 22,
                "count": 8,
                "no_return": 0,
            }
        ],
    }
}
```

# Params
```python
{
    {
        "rrr": 15.25,
        "runs": 999,
    }
}
```

# Recipe Result
```python
{
    "inputs": [
        {
            "name": "Arcane Agaric [2.0]",
            "quantity": 0,
            "price": 0,
            "total": 0,
            "setup_fee": 0,
            "sales_tax": 0,
        }
    ],
    "outputs": [
        {
            "name": "Minor Energy Potion [2.0]",
            "quantity": 0,
            "price": 274,
            "total": 0,
            "setup_fee": 0,
            "sales_tax": 0,
        }
    ],
    "extras": [
        {
            "name": "Arcane Agaric [2.0]",
            "quantity": 0,
            "price": 0,
            "total": 0,
            "setup_fee": 0,
            "sales_tax": 0,
        }
    ],
    "misc": {
        "income": 0,
        "sales_fee": 0,
        "expence": 0.0,
        "profit": 0.0,
        "roi": 0,
        "missing_prices": True,
        "usage_fee": 0.0,
    },
}
```