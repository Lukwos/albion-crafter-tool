from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from albion_crafter_tool import albion_data, aodp_data


class DailyBonus(Widget):
    DEFAULT_CSS = """
    DailyBonus {
        border: round $primary;
        height: auto;
    }
    """

    BORDER_TITLE = "Daily Bonus"

    def __init__(self):
        super().__init__()
        self.daily_bonuses = albion_data.get_event_bonuses(
            [e["UniqueName"] for e in aodp_data.get_daily_events()["Events"]]
        )

    def compose(self) -> ComposeResult:
        yield Static()

    def on_mount(self) -> None:
        lines = []
        for bonus in self.daily_bonuses:
            lines.append(f"{bonus['name']:<20} : {bonus['value'] * 100} %")
        self.query_one(Static).content = "\n".join(lines)
