from textual.app import App, ComposeResult, on
from textual.binding import Binding
from textual.containers import Container, HorizontalGroup
from textual.events import Print
from textual.widgets import (
    Checkbox,
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

import albion_data


class AlbionCrafterToolApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [Binding("ctrl+u", "update_recipes", "Update Recipes")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent():
            with TabPane("Setup"):
                with HorizontalGroup():
                    with Container(id="left_panel"):
                        yield Label("Have Premium")
                        yield Checkbox()
                        yield Label("Use Focus")
                        yield Checkbox()
                        yield Label("Locations")
                        yield Select((c, c) for c in albion_data.LOCATIONS)
                        yield Label("Daily Sold %")
                        yield Input()
                        yield Label("Craft Fees")
                        yield Input()
                    with Container(id="right_panel"):
                        yield Label("Search Category")
                        category_input = Input(id="category_input")
                        yield category_input
                        yield AutoComplete(
                            category_input, candidates=self.candidates_callback
                        )
                        yield Label("Select Tiers")
                        yield SelectionList(*albion_data.TIERS)
                yield Log(max_lines=80, auto_scroll=True)
            with TabPane("Missing Prices"):
                yield DataTable(id="missing_prices_datatable")
            with TabPane("Recipes"):
                yield DataTable(id="recipes_datatable")
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
        self.query_one("#recipes_datatable", DataTable).add_columns(
            "ID", "Name", "Run", "ROI", "Profit"
        )
        self.categories = set()
        self.recipes = []
        self.useful_items = set()

    def on_print(self, event: Print):
        self.query_one(Log).write(event.text)

    def candidates_callback(self, state: TargetState) -> list[DropdownItem]:
        if not state.text:
            return []
        matches = albion_data.search_category(state.text)[:10]
        return [DropdownItem(c["path"]) for c in matches]  # prefix=c["name"]

    def _action_update_recipes(self):
        print("Update Recipes")
        self.recipes, self.useful_items = (
            albion_data.compute_all_recipes_from_categories(self.categories)
        )
        self.update_recipe_datatable()
        self.update_missing_prices_datatable()
        self.query_one("#debug_data", Pretty).update(self.recipes)

    def update_recipe_datatable(self):
        datatable = self.query_one("#recipes_datatable", DataTable)
        for recipe in self.recipes:
            datatable.add_row(recipe["item_name"], recipe["amount_crafted"])
            for line in recipe["lines"]:
                datatable.add_row(None, None, line["item_name"], line["count"])

    def update_missing_prices_datatable(self):
        datatable = self.query_one("#missing_prices_datatable", DataTable)
        for item in self.useful_items:
            print(item)

    @on(Input.Submitted, "#category_input")
    def on_category_input_submitted(self, event: Input.Submitted):
        self.categories.add(event.value)
        event.control.clear()


app = AlbionCrafterToolApp()
if __name__ == "__main__":
    app.run()
