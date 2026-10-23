from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from albion_crafter_tool import albion_data, aodp_data


class DailyBonus(Widget):
    def compose(self) -> ComposeResult:
        yield Static()

    def __init__(self):
        super().__init__()
        self.daily_bonuses = albion_data.get_event_bonuses(
            [e["UniqueName"] for e in aodp_data.get_daily_events()["Events"]]
        )

    def on_mount(self) -> None:
        self.query_one(Static).content = str(self.daily_bonuses)
