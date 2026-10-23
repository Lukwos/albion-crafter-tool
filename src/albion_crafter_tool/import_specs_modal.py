from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Label, Button, Pretty, Footer, DataTable, Header, TextArea
from textual import on
from albion_crafter_tool import albion_data


class ImportSpecsModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "import_specs", "Confirm"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield TextArea(placeholder="Paste text from AlbionFreeMarket specs menu")
            yield Footer()

    def action_cancel(self):
        self.dismiss()

    def action_import_specs(self):
        text = self.query_one(TextArea).text
        update = albion_data.import_afm_specs(text)
        self.notify(f"{update} specs have been updated")
        self.dismiss()
