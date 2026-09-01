# Approach

## What I had

A Mac and an iPhone. That decided most of the stack:

- **taky** as the TAK server. It is Python, runs on macOS, and needs no cloud account.
  The alternative, TAK Server itself, is Java and heavier than this task needs.
- **iTAK** on the iPhone — the iOS client. ATAK is Android only, so iTAK it is.
- **Docker** for signal-cli-rest-api, so Signal's Java tooling stays in a container
  instead of on the Mac.
- **Python 3.14** for the bot, same language as taky, and the venv holds both.

## Two repos that set the shape

1. [bbernhard/signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) —
   wraps signal-cli in an HTTP API and a linked-device QR flow. No Signal protocol work.
2. [tkuester/taky](https://github.com/tkuester/taky) — a TAK server plus `takyctl`, which
   generates the CA, the certificates and a ready-to-import iTAK client package.

Between them, the bot only has to build a CoT event and write it to a socket. That is why
it came together quickly.

## Challenges

**Signal has no official bot API.** There is no documented way to build one, so the search
was for open source instead. signal-cli wrapped by signal-cli-rest-api was the shortest
path — the bot is a linked device on a normal account, not a bot account.

**No Android device.** ATAK is Android only, and the official TAK Server is Java. taky runs
on the Mac and pairs with iTAK on the iPhone, so the whole path stays on hardware I have.

**Certificates are issued for an IP, not a hostname.** So `check_hostname` has to be off,
or the TLS handshake fails. Regenerating the CA also invalidates any client package already
imported on the phone.

**taky needs `setuptools`.** It imports `pkg_resources`, which venvs stopped bundling in
Python 3.12, so `taky` and `takyctl` fail at import without it.

## Decisions and assumptions

**Coordinate order.** The brief labels the sample `48.567123 39.87897` as longitude then
latitude. Read that way it lands in the Caspian Sea. Read latitude first it is eastern
Ukraine, the intended area — so the bot parses latitude first.

**The label picks the symbol.** `tank` and `truck` produce different CoT types, not one
generic marker. An unknown word falls back to plain hostile ground rather than guessing.

**Only confirm what happened.** The reply says the point was added only after the server
accepted the bytes. A refused connection gets a failure reply instead.

## Limitations

- TAK over TCP sends no acknowledgement, so "delivered" means the server took the bytes.
  It is not proof the marker rendered on the phone.
- Everything is hostile and ground. No friendly or air markers, no altitude, no accuracy —
  a typed report carries none of that.
- One label, one word. The regex takes a single token, so `armoured column` is not valid.
- The bot reuses taky's server keypair as its client certificate. Fine for a LAN test,
  wrong for anything real — the bot should have its own.