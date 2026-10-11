from textual.app import ComposeResult
from textual.widgets import Label
from textual.widget import Widget
from textual.containers import Container


class RecipeWidget(Widget):
    DEFAULT_CSS = """
        RecipeWidget {
            border: solid $primary;
        }

        #input_container {
            layout: grid;
            grid-size: 2;
            border: solid $secondary;
        }
        """

    def __init__(self, recipe) -> None:
        self.recipe = recipe
        print("Widget", self.recipe["item_name"])
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(self.recipe["item_name"])
        yield Label(str(self.recipe["amount_crafted"]))
        with Container(id="input_container"):
            for line in self.recipe["lines"]:
                yield Label(line["item_name"])
                yield Label(str(line["count"]))

    def on_mount(self):
        self.query_one("#input_container", Container).border_title = "Inputs"
