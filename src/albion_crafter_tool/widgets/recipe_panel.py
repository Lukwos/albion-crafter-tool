from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Label, Pretty

from albion_crafter_tool import albion_data, aodp_data


class RecipePanel(Widget):
    DEFAULT_CSS = """
    DailyBonus {
        border: round $primary;
        height: auto;
    }
    """

    BORDER_TITLE = "Recipe Line"

    def __init__(self, recipe):
        super().__init__()
        self._recipe = recipe
        self.params = {}
        self.result = {}

    def compose(self) -> ComposeResult:
        yield Label(self.recipe["item_name"])
        yield Pretty(self.recipe)
        yield Pretty(self.params)
        yield Pretty(self.result)

    def on_mount(self) -> None:
        pass

    def set_params(self, params):
        self.params = params
        self.recompose()

    def compute(self):
        pass
