"""What `bot.py` registers, and how narrowly.

`SignalBot.register` filters on contacts and groups independently, and the two are
OR'd: a message is handled if it matches *either*. `contacts` defaults to True, so
passing `groups=[...]` alone still lets every 1:1 direct message through — which for
this bot would put a marker on the map from a stranger's DM. These tests pin the
`contacts=False` that closes it.
"""

import bot
from commands import ATAKCommand, PingCommand

GROUP = "group.TESTGROUPID="


def registrations(mocker, monkeypatch):
    """Run `bot.main()` against a stand-in bot and return its register() calls."""
    monkeypatch.setenv("SIGNAL_SERVICE", "127.0.0.1:8080")
    monkeypatch.setenv("PHONE_NUMBER", "+441632960001")
    monkeypatch.setenv("GROUP_ID", GROUP)

    # Replaces the whole bot: no event loop, no storage, no sockets, no start().
    signal_bot = mocker.patch("bot.SignalBot").return_value
    bot.main()

    return signal_bot.register.call_args_list


def test_no_handler_listens_to_direct_messages(mocker, monkeypatch):
    calls = registrations(mocker, monkeypatch)

    assert calls, "bot.main() registered no handlers at all"
    for call in calls:
        handler = type(call.args[0]).__name__
        # `is False`, not falsy: an empty list would also pass a truthiness check
        # whilst meaning something different to signalbot.
        assert call.kwargs.get("contacts") is False, (
            f"{handler} accepts direct messages — "
            f"contacts={call.kwargs.get('contacts')!r}"
        )


def test_every_handler_is_scoped_to_the_configured_group(mocker, monkeypatch):
    calls = registrations(mocker, monkeypatch)

    for call in calls:
        handler = type(call.args[0]).__name__
        assert call.kwargs.get("groups") == [GROUP], (
            f"{handler} is not restricted to GROUP_ID — "
            f"groups={call.kwargs.get('groups')!r}"
        )


def test_both_handlers_are_registered(mocker, monkeypatch):
    registered = {
        type(call.args[0]) for call in registrations(mocker, monkeypatch)
    }

    assert registered == {PingCommand, ATAKCommand}
