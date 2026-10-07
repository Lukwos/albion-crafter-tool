from textual import on
from textual.events import Mount, Print
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import (
    DataTable,
    Footer,
    TabbedContent,
    TabPane,
    Markdown,
    Input,
    Header,
    SelectionList,
    Pretty,
    Button,
    Log,
    Label,
)

from main import *

missing_prices = []
reports = []


class TableApp(App):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent():
            with TabPane("Setup"):
                yield Container(
                    Label("Run"),
                    Input(compact=True),
                )
                yield SelectionList(*categories, id="c")
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
                yield Button("Update Recipes")
            with TabPane("Missing Prices"):
                yield DataTable(id="dt_1")
            with TabPane("Reports"):
                yield DataTable(id="dt_2")
        yield Log()

    def on_mount(self) -> None:
        self.begin_capture_print(self)
        table = self.query_one("#dt_1", DataTable)
        table.add_columns("Name", "City")
        # table.add_rows((b("@ITEMS", p[0]), p[1]) for p in missing_prices)

        table = self.query_one("#dt_2", DataTable)
        table.add_columns("ID", "Name", "Run", "ROI", "Profit")
        # table.add_rows(
        #     (r["name"], b("@ITEMS", r["name"]), r["run"], r["roi"], int(r["profit"]))
        #     for r in reports
        # )

    def on_print(self, event: Print):
        self.query_one(Log).write(event.text)

    @on(Mount)
    @on(SelectionList.SelectedChanged, "#c,#t")
    def update_recipe_list(self):
        item_datas = []
        item_list = set()
        tiers = self.query_one("#t", SelectionList).selected
        for category in self.query_one("#c", SelectionList).selected:
            for item in get_item_list_from_category(category, tiers):
                item_data = get_recipes(item)
                item_list |= get_item_list_from_item_data(item_data)
                item_datas.append(item_data)
        prices = get_prices(item_list)
        history = get_history(item_list)
        missing_prices = get_missing_prices(prices)

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.exit(str(event.button))


app = TableApp()
if __name__ == "__main__":
    app.run()
