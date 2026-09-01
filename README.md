# Signal → ATAK CoT Bot

A Signal bot that turns a text report into a Cursor on Target (CoT) event and pushes it to
an ATAK / iTAK client through a [taky](https://github.com/tkuester/taky) TAK server.

Send this to the Signal group:

```
48.567123 39.87897 tank
```

A hostile armour marker labelled `tank` appears on the map, at those coordinates. The label
picks the symbol — `truck` and `infantry` render differently — and the reply in the group
only claims the point was added once the CoT actually reached the server.

```
Signal app → signal-cli-rest-api (json-rpc, :8080) → bot.py
   → mutual-TLS TCP :8089 → taky → iTAK on iPhone
```

Stack: [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) · taky · iTAK.

## Documentation

- **[docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md)** — how to set it up and run it, start to
  finish: signal-cli, linking the phone, taky and its certificates, iTAK, the bot. Then the
  message format, the target-type table, the CoT protocol field by field, verification,
  troubleshooting and diagnostics.
- **[docs/APPROACH.md](docs/APPROACH.md)** — why this stack, the challenges hit along the
  way, the decisions and assumptions made, and what it deliberately does not do.

## Quick start

Already set up? Then:

```bash
source .venv/bin/activate
docker compose up -d                 # signal-cli-rest-api
cd taky-server && taky -c ./taky.conf &
python bot.py
```

Otherwise start at [docs/INSTRUCTIONS.md](docs/INSTRUCTIONS.md).

Tests need no Signal account, TAK server or certificates:

```bash
python -m pytest -q
```

## Layout

```
bot.py                    entrypoint — loads .env, registers handlers
commands/ping.py          "ping" → "pong", liveness check
commands/atak.py          Signal handler — validate, build, reply
utils/cot_utils.py        target types, coordinate validation, CoT build
services/tak_service.py   mutual-TLS delivery to the TAK server
tests/                    pytest suite
docs/                     setup instructions, approach, screenshots
docker-compose.yml        signal-cli-rest-api
.env.example              required variables
requirements.txt          bot dependencies
pytest.ini                pytest config only
taky-server/              taky config, CA and certificates (gitignored)
signal-cli-config/        Signal linked-account credentials (gitignored)
```
