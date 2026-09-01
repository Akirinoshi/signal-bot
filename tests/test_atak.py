"""Handler-level tests: what the group sees, and what reaches the TAK service."""

from unittest.mock import AsyncMock, MagicMock

from signalbot.test_utils import ChatTestCase, mock_chat

from commands.atak import ATAKCommand
from services.tak_service import TakDeliveryError, TakService


def stub_tak(**kwargs) -> MagicMock:
    """A TakService that records what it was handed instead of opening a socket."""
    return MagicMock(spec=TakService, **kwargs)


def only_reply(send_mock) -> str:
    """Text of the single message the bot sent."""
    assert send_mock.call_count == 1
    return next(iter(send_mock.results())).message


class TestATAKChat(ChatTestCase):
    # `setup_method`, not `setup`: pytest >=8 no longer calls nose-style `setup`
    def setup_method(self, method):
        super().setup()
        self.tak = stub_tak()
        self.signal_bot.register(ATAKCommand(tak=self.tak))

    @mock_chat("48.567123 39.87897 tank")
    async def test_valid_report_is_transmitted_and_confirmed(self, mocker):
        self.tak.send.assert_awaited_once()

        cot_xml = self.tak.send.call_args.args[0]
        assert b'callsign="tank"' in cot_xml
        assert b'lat="48.567123"' in cot_xml

        assert only_reply(self.send_mock) == (
            "Added tank to the map at 48.567123, 39.87897"
        )

    @mock_chat("999.9 999.9 tank")
    async def test_out_of_range_report_is_not_transmitted(self, mocker):
        # Rejected before the service is reached, so nothing can leave the bot.
        self.tak.send.assert_not_called()

        reply = only_reply(self.send_mock)
        assert "Could not add tank" in reply
        assert "latitude 999.9 is outside ±90" in reply


class TestATAKChatServerDown(ChatTestCase):
    def setup_method(self, method):
        super().setup()
        failure = TakDeliveryError(
            "192.168.1.42:8089", ConnectionRefusedError("refused")
        )
        self.tak = stub_tak(send=AsyncMock(side_effect=failure))
        self.signal_bot.register(ATAKCommand(tak=self.tak))

    @mock_chat("48.567123 39.87897 tank")
    async def test_failed_delivery_is_reported_not_claimed(self, mocker):
        reply = only_reply(self.send_mock)
        assert reply.startswith("Could not add tank to the map")
        assert "192.168.1.42:8089 unreachable" in reply
        assert "Added" not in reply