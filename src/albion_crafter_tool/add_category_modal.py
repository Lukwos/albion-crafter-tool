from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import TextArea, Input, OptionList
from textual import on
from albion_crafter_tool import albion_data
from textual.widgets.option_list import Option


class AddCategoryModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Input()
            yield OptionList()

    def action_cancel(self):
        self.dismiss()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected):
        self.dismiss(event.option_id)

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed):
        categories = (
            albion_data.search_category(event.value)[:10] if event.value else []
        )
        option_list: OptionList = self.query_one(OptionList)
        option_list.clear_options()
        option_list.add_options(
            Option(f"{c['name']} ({c['path']})", id=c["path"]) for c in categories
        )
