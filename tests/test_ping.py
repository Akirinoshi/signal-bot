from signalbot.test_utils import ChatTestCase, mock_chat

from commands.ping import PingCommand


class TestPingChat(ChatTestCase):
    # `setup_method`, not `setup`: pytest >=8 no longer calls nose-style `setup`
    def setup_method(self, method):
        super().setup()
        self.signal_bot.register(PingCommand())

    @mock_chat("ping")
    async def test_ping(self, mocker):
        assert self.send_mock.call_count == 1
        for sent in self.send_mock.results():
            assert sent.recipients == [ChatTestCase.group_id]
            assert sent.message == "pong"