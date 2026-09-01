"""Signal handler that turns a typed target report into a CoT event on the map.

`<latitude> <longitude> <label>` in the group becomes one CoT event, pushed to
the taky server, which fans it out to connected ATAK / iTAK clients. CoT
construction and validation live in `utils.cot_utils`, delivery in
`services.tak_service`; this module is the Signal side only.
"""

from signalbot import (
    DataMessageContext,
    DataMessageHandler,
    SendMessage,
    regex_triggered,
)
from datetime import datetime, timezone

from services.tak_service import TakDeliveryError, TakService
from utils.cot_utils import build_cot, coord_error


class ATAKCommand(DataMessageHandler):
    """Places a marker on the ATAK map from a coordinate message in the group."""

    COORD_RE = r"^\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\S+)\s*$"

    def __init__(self, tak: TakService | None = None):
        super().__init__()
        self.tak = tak or TakService()

    @regex_triggered(COORD_RE)
    async def handle_data_message(self, c: DataMessageContext):
        """Validate the report, transmit it, and reply with what actually happened."""
        lat, lon, label = c.message.text.split()

        error = coord_error(lat, lon)
        if error:
            await c.send(SendMessage(
                text=f"Could not add {label} to the map — {error}. "
                     f"Expected: <latitude ±90> <longitude ±180> <label>, "
                     f"e.g. 48.567123 39.87897 tank"
            ))
            return

        cot_xml = build_cot(lat, lon, label, datetime.now(timezone.utc))

        # Only claim the marker was added if the CoT actually reached the server.
        try:
            await self.tak.send(cot_xml)
        except TakDeliveryError as e:
            await c.send(SendMessage(
                text=f"Could not add {label} to the map — {e}."
            ))
            return

        await c.send(SendMessage(
            text=f"Added {label} to the map at {lat}, {lon}"
        ))