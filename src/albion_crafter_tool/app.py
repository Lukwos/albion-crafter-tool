import albion_data
import compute
import aodp_data
from recipe_details_modal import RecipeDetailsModal
from textual.reactive import reactive
from textual.app import App, ComposeResult, on
from textual.binding import Binding
from textual.containers import Container, HorizontalGroup, VerticalScroll, Grid
from textual.events import Print
from textual.widgets import (
    Checkbox,
    ListView,
    ListItem,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Pretty,
    Select,
    SelectionList,
    TabbedContent,
    TabPane,
    OptionList,
    TextArea,
)
from textual_autocomplete import AutoComplete
from textual_autocomplete._autocomplete import DropdownItem, TargetState
from textual.theme import Theme
from textual.widgets.option_list import Option
import math
from import_specs_modal import ImportSpecsModal
from add_category_modal import AddCategoryModal

ALBION_THEME = Theme(
    name="albion-online",
    primary="#D4A373",  # Doré d'Albion (Interface, Or, Rareté)
    secondary="#8B5A2B",  # Marron Cuir/Terre (Équipement, Nature)
    accent="#E63946",  # Rouge Hostile (PvP, Danger, Alertes)
    background="#1A1512",  # Brun très sombre (Fond d'interface médiéval)
    surface="#2C221E",  # Brun moyen (Fonds des panneaux et conteneurs)
    panel="#3D302A",  # Brun clair (Focus, surbrillance d'éléments)
    success="#4C9A2A",  # Vert Émeraude (Zone sûre, Récolte, Soin)
    warning="#E9C46A",  # Jaune Ambre (Zone Jaune, Attention)
    error="#D62828",  # Rouge Sang (Zone Rouge/Noire, Échec)
    # info="#4EA8DE",  # Bleu Magie (Énergie, Mana, Factions)
)


class AlbionCrafterToolApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+a", "update_recipes", "Update Recipes"),
        Binding("ctrl+z", "update_prices", "Update Prices"),
        Binding("ctrl+e", "import_specs", "Import Specs"),
        Binding("a", "add_category", "Add Category"),
        Binding("p", "toggle_premium", "Premium"),
        Binding("f", "toggle_focus", "Focus"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="main"):
            with Container(id="setup"):
                yield OptionList(id="category_list", compact=True)
                yield Checkbox(
                    "Have Premium", value=True, id="have_premium", disabled=True
                )
                yield Checkbox("Use Focus", id="use_focus", disabled=True)
                yield Label("Focus")
                yield Input(value="10000", id="focus_input", compact=True)
                yield Label("Location")
                yield Select(
                    ((c, c) for c in albion_data.LOCATIONS),
                    value="Lymhurst",
                    id="location",
                    compact=True,
                )
                yield Label("Craft Fee")
                yield Input(value="300", id="craft_fees", compact=True)
            with Container(id="missing_prices"):
                yield DataTable(id="missing_prices_datatable")
            with Container(id="recipes"):
                yield DataTable(id="recipe_datatable", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.begin_capture_print(self)
        self.register_theme(ALBION_THEME)
        self.theme = "albion-online"

        self.query_one("#setup").border_title = "Setup"
        self.query_one("#missing_prices").border_title = "Missing Prices"
        self.query_one("#recipes").border_title = "Recipes"

        self.query_one("#recipe_datatable", DataTable).add_columns(
            "Name", "Runs", "Profit", "ROI", "Missing Prices"
        )
        self.query_one("#missing_prices_datatable", DataTable).add_columns(
            "Name", "Location"
        )
        self.categories = set(["/consumables/potions/energy"])
        self.recipes = []
        self.all_items = set()
        self.all_prices = []
        self.price_history = []
        self.daily_sold_percentage = 1
        self.premium = True
        self.focus = False

    def candidates_callback(self, state: TargetState) -> list[DropdownItem]:
        if not state.text:
            return []
        matches = albion_data.search_category(state.text)[:10]
        return [DropdownItem(c["path"]) for c in matches]  # prefix=c["name"]

    def action_update_recipes(self):
        self.recipes, self.all_items = albion_data.compute_all_recipes_from_categories(
            self.categories
        )
        self._update_recipe_datatable()

    def _update_recipe_datatable(self):
        recipe_datatable: DataTable = self.query_one("#recipe_datatable", DataTable)
        recipe_datatable.clear()
        for recipe in self.recipes:
            recipe_datatable.add_row(
                recipe["item_name"],
                recipe.get("runs", None),
                recipe.get("result", {}).get("misc", {}).get("profit"),
                recipe.get("result", {}).get("misc", {}).get("roi"),
                recipe.get("result", {}).get("misc", {}).get("missing_prices"),
                key=recipe["id"],
            )

    def action_update_prices(self):
        self._update_prices()

    def _update_prices(self):
        location = self.query_one("#location").value
        self.all_prices = aodp_data.get_prices(
            ",".join(i["xml_id"] for i in self.all_items),
            locations=location,
        )
        self.price_history = aodp_data.get_price_history(
            ",".join(i["xml_id"] for i in self.all_items)
        )
        self._update_visual_missing_prices()
        self._update_recipes_result()

    def _update_visual_missing_prices(self):
        datatable = self.query_one("#missing_prices_datatable", DataTable)
        datatable.clear()
        missing_prices = aodp_data.get_missing_prices(self.all_prices)
        for item, location in missing_prices:
            datatable.add_row(item, location)

    def _update_recipes_result(self):
        for recipe in self.recipes:
            focus_item_qty = albion_data.get_item_quantity_from_focus(
                recipe["item_xml_id"],
                recipe["amount_crafted"],
                recipe["crafting_focus"],
                10_000,
            )
            daily_sold = aodp_data.compute_daily_sold(
                recipe["item_xml_id"],
                self.price_history,
                city=self.query_one("#location").value,
            )
            runs = min(
                math.floor(
                    (daily_sold * (self.daily_sold_percentage))
                    // recipe["amount_crafted"]
                ),
                focus_item_qty // recipe["amount_crafted"],
            )
            recipe["with"] = {
                "focus_used": 10_000,
                "focus_qty": focus_item_qty,
                "daily_qty": daily_sold,
                "daily_percentage": self.daily_sold_percentage,
                "runs": runs,
            }
            recipe["result"] = compute.compute_recipe(
                recipe,
                self.all_prices,
                int(self.query_one("#craft_fees").value),
                self.query_one("#use_focus").value,
                self.query_one("#have_premium").value,
            )
        self.recipes = sorted(
            self.recipes, key=lambda r: r["result"]["misc"]["roi"], reverse=True
        )
        self._update_recipe_datatable()

    @on(DataTable.RowSelected, "#recipe_datatable")
    def on_recipe_row_selected(self, event: DataTable.RowSelected):
        self.push_screen(RecipeDetailsModal(self.recipes[event.cursor_row]))

    @on(DataTable.CellSelected, "#missing_prices_datatable")
    def on_missing_prices_cell_selected(self, event: DataTable.CellSelected):
        self.copy_to_clipboard(event.value)

    def _update_category_list(self):
        category_list = self.query_one("#category_list")
        category_list.clear_options()
        category_list.add_options(c for c in self.categories)

    def action_import_specs(self):
        self.push_screen(ImportSpecsModal())

    def action_add_category(self):
        self.push_screen(AddCategoryModal(), self.callback_add_category_modal)

    def callback_add_category_modal(self, result):
        self.categories.add(result)
        self._update_category_list()

    def action_toggle_premium(self):
        self.premium = not self.premium
        self.notify(f"Premium set to {self.premium}")

    def action_toggle_focus(self):
        self.focus = not self.focus
        self.notify(f"Focus set to {self.focus}")


app = AlbionCrafterToolApp()
if __name__ == "__main__":
    app.run()
