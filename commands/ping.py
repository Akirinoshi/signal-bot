"""Liveness check: "ping" in the group gets "pong" back.

Cheapest confirmation that Signal, signal-cli-rest-api and the bot pipeline are
all talking, with no TAK server involved.
"""

from signalbot import (
    DataMessageContext,
    DataMessageHandler,
    SendMessage,
    text_triggered,
)


class PingCommand(DataMessageHandler):
    """Replies "pong" to "ping"."""

    @text_triggered("ping")
    async def handle_data_message(self, c: DataMessageContext):
        """Answer the liveness probe."""
        await c.send(SendMessage(text="pong"))