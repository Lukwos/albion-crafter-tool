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
)
from textual_autocomplete import AutoComplete
from textual_autocomplete._autocomplete import DropdownItem, TargetState
from textual.theme import Theme
from textual.widgets.option_list import Option

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
        Binding("&", "update_recipes", "Update Recipes"),
        Binding("é", "update_prices", "Update Prices"),
        Binding("p", "toggle_premium", "Toggle Premium"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="main"):
            with Container():
                yield Input(id="category_input", compact=True)
                yield OptionList(compact=True, id="category_selection_list")
            with Container(id="setup"):
                yield OptionList(id="category_list", compact=True)
                yield Checkbox("Have Premium", value=True, id="have_premium")
                yield Checkbox("Use Focus", id="use_focus")
                yield Label("Location")
                yield Select(
                    ((c, c) for c in albion_data.LOCATIONS),
                    value="Lymhurst",
                    id="location",
                    compact=True,
                )
                yield Label("Craft Fee")
                yield Input(value="300", id="craf_fees", compact=True)
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
            "Name", "Runs", "Profit", "ROI"
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

    def candidates_callback(self, state: TargetState) -> list[DropdownItem]:
        if not state.text:
            return []
        matches = albion_data.search_category(state.text)[:10]
        return [DropdownItem(c["path"]) for c in matches]  # prefix=c["name"]

    @on(Input.Submitted, "#category_input")
    def on_category_input_submitted(self, event: Input.Submitted):
        self.categories.add(event.value)
        event.control.clear()

    def action_update_recipes(self):
        self.recipes, self.all_items = albion_data.compute_all_recipes_from_categories(
            self.categories
        )
        self._update_recipe_datatable()

    def _update_recipe_datatable(self):
        recipe_datatable: DataTable = self.query_one("#recipe_datatable", DataTable)
        recipe_datatable.clear()
        for recipe in filter(
            lambda r: (
                not r.get("result", {}).get("misc", {}).get("missing_prices", False)
                and r.get("runs", None)
            ),
            self.recipes,
        ):
            recipe_datatable.add_row(
                recipe["item_name"],
                recipe.get("runs", None),
                recipe.get("result", {}).get("misc", {}).get("profit"),
                recipe.get("result", {}).get("misc", {}).get("roi"),
                key=recipe["id"],
            )

    def action_update_prices(self):
        self._update_prices()

    def _update_prices(self):
        self.all_prices = aodp_data.get_prices(
            ",".join(i["xml_id"] for i in self.all_items)
        )
        self.price_history = aodp_data.get_price_history(
            ",".join(i["xml_id"] for i in self.all_items)
        )
        self._update_visual_missing_prices()
        self._update_recipes_result()

    def _update_visual_missing_prices(self):
        datatable = self.query_one("#missing_prices_datatable", DataTable)
        missing_prices = aodp_data.get_missing_prices(self.all_prices)
        for item, location in missing_prices:
            datatable.add_row(item, location)

    def _update_recipes_result(self):
        for recipe in self.recipes:
            daily_sold = aodp_data.compute_daily_sold(
                recipe["item_xml_id"], self.price_history
            )
            runs = int(
                (daily_sold * (self.daily_sold_percentage)) // recipe["amount_crafted"]
            )
            recipe["daily_sold"] = daily_sold
            recipe["runs"] = runs
            recipe["result"] = compute.compute_recipe(recipe, self.all_prices)
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

    @on(Input.Changed, "#category_input")
    def on_input_changed(self, event: Input.Changed):
        categories = (
            albion_data.search_category(event.value)[:10] if event.value else []
        )
        option_list: OptionList = self.query_one("#category_selection_list", OptionList)
        option_list.clear_options()
        option_list.add_options(
            Option(f"{c['name']} ({c['path']})", id=c["path"]) for c in categories
        )

    @on(OptionList.OptionSelected, "#category_selection_list")
    def on_option_selected(self, event: OptionList.OptionSelected):
        self.categories.add(event.option_id)
        self.query_one("#category_input").clear()
        self.query_one("#category_input").focus()
        self._update_category_list()

    def _update_category_list(self):
        category_list = self.query_one("#category_list")
        category_list.clear_options()
        category_list.add_options(c for c in self.categories)


app = AlbionCrafterToolApp()
if __name__ == "__main__":
    app.run()
