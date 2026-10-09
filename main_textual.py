from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, HorizontalGroup, Vertical
from textual.events import Mount, Print
from textual.suggester import SuggestFromList
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Markdown,
    Pretty,
    Select,
    SelectionList,
    TabbedContent,
    TabPane,
    Tree,
)
from textual_autocomplete import AutoComplete
from textual_autocomplete._autocomplete import DropdownItem, TargetState

from main import *

missing_prices = []
reports = []
CITIES = {"Lymhurst", "Fort Sterling"}


class CustomSuggestFromList(SuggestFromList):
    async def get_suggestion(self, value: str) -> str | None:
        for idx, suggestion in enumerate(self._for_comparison):
            if value in suggestion:
                return self._suggestions[idx]
        return None


class AlbionCrafterToolApp(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [Binding("ctrl+u", "update_recipes", "Update Recipes", priority=True)]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent():
            with TabPane("Setup"):
                with HorizontalGroup():
                    with Container(id="left_panel"):
                        yield Label("Have Premium")
                        yield Checkbox()
                        yield Label("City")
                        yield Select(((c, c) for c in CITIES))
                        yield Label("Daily Sold %")
                        yield Input()
                    with Container(id="right_panel"):
                        yield Label("Search Category")
                        category_input = Input(id="category_input")
                        yield category_input
                        yield AutoComplete(
                            category_input, candidates=self.candidates_callback
                        )
                        yield Label("Select Tiers")
                        yield SelectionList(
                            *[
                                ("I", 1),
                                ("II", 2),
                                ("III", 3),
                                ("IV", 4),
                                ("V", 5),
                                ("VI", 6),
                                ("VII", 7),
                                ("VIII", 8),
                            ],
                            id="t",
                        )
                yield Log()
            with TabPane("Missing Prices"):
                yield DataTable(id="dt_1")
            with TabPane("Reports"):
                yield DataTable(id="dt_2")
            with TabPane("Specs"):
                yield Pretty(specs)
            with TabPane("Shop Categories"):
                yield Pretty(categories)

    def on_mount(self) -> None:
        self.begin_capture_print(self)
        print("On Mount : OK")
        self.query_one("#dt_1", DataTable).add_columns("Name", "City")
        self.query_one("#dt_2", DataTable).add_columns(
            "ID", "Name", "Run", "ROI", "Profit"
        )
        self.selected_categories = set()

    def on_print(self, event: Print):
        self.query_one(Log).write(event.text)

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted):
        self.selected_categories.add(event.value)
        print(self.selected_categories)
        self.query_one("#category_input", Input).clear()

    def candidates_callback(self, state: TargetState) -> list[DropdownItem]:
        matches = [i for i in categories if state.text in i][:10]
        return [DropdownItem(item) for item in matches]

    def action_update_recipes(self):
        print("=== Update Recipes ...")
        item_datas = []
        item_list = set()
        tiers = self.query_one("#t", SelectionList).selected
        print("categories")
        for category in self.selected_categories:
            print(category)
            print("items")
            for item in get_item_list_from_category(category, tiers):
                print(item)
                item_data = get_recipes(item)
                item_list |= get_item_list_from_item_data(item_data)
                item_datas.append(item_data)
        print("item_list")
        print(item_list)
        # prices = get_prices(item_list)
        # history = get_history(item_list)
        # missing_prices = get_missing_prices(prices)
        # print("missing_prices")
        # print(missing_prices)

        table = self.query_one("#dt_1", DataTable)
        table.clear()
        table.add_rows((b("@ITEMS", p[0]), p[1]) for p in missing_prices)

        reports = []
        for item_data in item_datas:
            for recipe in item_data["recipes"]:
                daily_sold = compute_daily_sold(item_data["name"], history)
                report = compute_recipe(item_data["name"], recipe, prices, daily_sold)
                reports.append(report)

                table = self.query_one("#dt_2", DataTable)
                table.add_rows(
                    (
                        report["name"],
                        b("@ITEMS", report["name"]),
                        report["run"],
                        report["roi"],
                        int(report["profit"]),
                    )
                    for r in reports
                )

        reports = sorted(
            filter(lambda r: not r["missing_price"], reports),
            key=lambda r: r["roi"],
            reverse=True,
        )


app = AlbionCrafterToolApp()
if __name__ == "__main__":
    app.run()
