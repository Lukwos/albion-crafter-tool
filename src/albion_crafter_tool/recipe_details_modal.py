from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Label, Button, Pretty, Footer, DataTable, Header
from textual import on


class RecipeDetailsModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, recipe):
        super().__init__()
        self.recipe = recipe

    def compose(self) -> ComposeResult:
        with Vertical(id="modal"):
            with Container(id="inputs"):
                yield DataTable()
            with Container(id="extras"):
                yield DataTable()
            with Container(id="outputs"):
                yield DataTable()
            yield Pretty(self.recipe)
            yield Footer()

    def on_mount(self):
        inputs = self.query_one("#inputs", Container)
        inputs.border_title = "Inputs"
        dt = inputs.query_one(DataTable)
        dt.add_columns(
            "Name",
            "Quantity",
            "Price",
            "Total",
            "Setup Fee",
            "Sales Tax",
        )
        dt.add_rows(
            (
                l["name"],
                l["quantity"],
                l["price"],
                l["total"],
                l["setup_fee"],
                l["sales_tax"],
            )
            for l in self.recipe.get("result", {}).get("inputs", [])
        )

        extras = self.query_one("#extras", Container)
        extras.border_title = "Extras"
        dt = extras.query_one(DataTable)
        dt.add_columns(
            "Name",
            "Quantity",
            "Price",
            "Total",
            "Setup Fee",
            "Sales Tax",
        )
        dt.add_rows(
            (
                l["name"],
                l["quantity"],
                l["price"],
                l["total"],
                l["setup_fee"],
                l["sales_tax"],
            )
            for l in self.recipe.get("result", {}).get("extras", [])
        )
        outputs = self.query_one("#outputs", Container)
        outputs.border_title = "Outputs"
        dt = outputs.query_one(DataTable)
        dt.add_columns(
            "Name",
            "Quantity",
            "Price",
            "Total",
            "Setup Fee",
            "Sales Tax",
        )
        dt.add_rows(
            (
                l["name"],
                l["quantity"],
                l["price"],
                l["total"],
                l["setup_fee"],
                l["sales_tax"],
            )
            for l in self.recipe.get("result", {}).get("outputs", [])
        )

    def action_cancel(self):
        self.dismiss()
