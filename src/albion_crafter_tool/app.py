import albion_data
import aodp_data
import compute
from recipe_widget import RecipeWidget
from textual.app import App, ComposeResult, on
from textual.binding import Binding
from textual.containers import Container, HorizontalGroup
from textual.events import Print
from textual.widgets import (
    Switch,
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
)
from textual_autocomplete import AutoComplete
from textual_autocomplete._autocomplete import DropdownItem, TargetState


class AlbionCrafterToolApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        Binding("r", "update_recipes", "Update Recipes"),
        Binding("p", "update_prices", "Update Prices"),
        Binding("a", "update_runs", "Update Prices"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent():
            with TabPane("Setup"):
                with HorizontalGroup():
                    with Container(id="left_panel"):
                        yield Label("Have Premium")
                        yield Switch(value=True)
                        yield Label("Use Focus")
                        yield Switch()
                        yield Label("Locations")
                        yield Select(
                            ((c, c) for c in albion_data.LOCATIONS),
                            value="Lymhurst",
                            compact=True,
                        )
                        yield Label("Daily Sold %")
                        yield Input(
                            id="daily_sold_percentage_input",
                            type="number",
                            value="20",
                            compact=True,
                        )
                        yield Label("Craft Fees")
                        yield Input(value="300", compact=True)
                    with Container(id="right_panel"):
                        yield Label("Search Category")
                        category_input = Input(id="category_input", compact=True)
                        yield category_input
                        yield AutoComplete(
                            category_input, candidates=self.candidates_callback
                        )
                        yield Label("Select Tiers")
                        yield SelectionList(*albion_data.TIERS, compact=True)
                yield Log(max_lines=80, auto_scroll=True)
            with TabPane("Missing Prices"):
                yield DataTable(id="missing_prices_datatable")
            with TabPane("Recipes"):
                yield Container(id="recipes_container")
            with TabPane("Specs"):
                yield Pretty(albion_data.SPECS)
            with TabPane("Shop Categories"):
                yield Pretty(albion_data.LOCATIONS)
            with TabPane("Debug Data"):
                yield Pretty(None, id="debug_data")

    def on_mount(self) -> None:
        self.begin_capture_print(self)
        print("On Mount : OK")
        self.query_one("#missing_prices_datatable", DataTable).add_columns(
            "Name", "Location"
        )
        self.categories = set(["/consumables/potions/energy"])
        self.recipes = []
        self.all_items = set()
        self.all_prices = []

    def on_print(self, event: Print):
        self.query_one(Log).write(event.text)

    def candidates_callback(self, state: TargetState) -> list[DropdownItem]:
        if not state.text:
            return []
        matches = albion_data.search_category(state.text)[:10]
        return [DropdownItem(c["path"]) for c in matches]  # prefix=c["name"]

    def action_update_recipes(self):
        print("Update Recipes")
        print("Categories", self.categories)
        self.recipes, self.all_items = albion_data.compute_all_recipes_from_categories(
            self.categories
        )
        self.query_one("#debug_data", Pretty).update(self.all_items)
        self.update_recipe_widgets()

    def action_update_prices(self):
        self.all_prices = aodp_data.get_prices(
            ",".join(i["xml_id"] for i in self.all_items)
        )
        self.price_history = aodp_data.get_price_history(
            ",".join(i["xml_id"] for i in self.all_items)
        )
        self.update_missing_prices_datatable()

    def action_update_runs(self):
        for recipe in self.recipes:
            daily_sold_percentage = int(
                self.query_one("#daily_sold_percentage_input", Input).value
            )
            run = (
                aodp_data.compute_daily_sold(recipe["item_xml_id"], self.price_history)
                * (daily_sold_percentage / 100)
                // recipe["amount_crafted"]
            )
            print(run)

    def update_recipe_widgets(self):
        recipes_container = self.query_one("#recipes_container", Container)
        for recipe in self.recipes:
            recipes_container.mount(RecipeWidget(recipe))

    def update_missing_prices_datatable(self):
        datatable = self.query_one("#missing_prices_datatable", DataTable)
        missing_prices = aodp_data.get_missing_prices(self.all_prices)
        for item, location in missing_prices:
            print("Missing", item, location)
            datatable.add_row(item, location)
        self.update_one_recipe()

    def update_one_recipe(self):
        recipe = self.recipes[0]
        daily_sold = aodp_data.compute_daily_sold(
            recipe["item_xml_id"], self.price_history
        )
        compute.compute_recipe(recipe, self.all_prices, daily_sold)

    @on(Input.Submitted, "#category_input")
    def on_category_input_submitted(self, event: Input.Submitted):
        self.categories.add(event.value)
        event.control.clear()


app = AlbionCrafterToolApp()
if __name__ == "__main__":
    app.run()
