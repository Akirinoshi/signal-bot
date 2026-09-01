import logging
import os

from dotenv import load_dotenv
from signalbot import SignalBot

from commands import PingCommand, ATAKCommand

logging.getLogger().setLevel(logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def main():
    load_dotenv()

    signal_service = os.environ["SIGNAL_SERVICE"]
    phone_number = os.environ["PHONE_NUMBER"]
    group_id = os.environ["GROUP_ID"]

    config = {
        "signal_service": signal_service,
        "phone_number": phone_number,
        "storage": {"type": "in-memory"},
        "logging_level": logging.INFO,
    }
    bot = SignalBot(config)

    bot.register(PingCommand(), groups=[group_id])
    bot.register(ATAKCommand(), groups=[group_id])

    bot.start()


if __name__ == "__main__":
    main()