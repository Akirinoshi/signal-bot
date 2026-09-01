"""Transport to the TAK server: mutual-TLS delivery of CoT events.

Everything about *how* a CoT event reaches taky lives here — certificates, the
socket, the stream framing — so the Signal handler only has to decide what to
tell the operator afterwards.
"""

from pathlib import Path
import asyncio
import logging
import os
import socket
import ssl

# Resolved from this file, not the working directory, so the bot can be started
# from anywhere. services/tak_service.py -> project root -> taky-server/ssl
SSL_DIR = Path(__file__).resolve().parent.parent / "taky-server" / "ssl"

# CoT is a stream protocol: one event per null-terminated document. That
# delimiter is how the TAK server finds message boundaries.
COT_DELIMITER = b"\x00"

CONNECT_TIMEOUT = 5
DEFAULT_PORT = 8089


class TakDeliveryError(Exception):
    """The event never left the bot. Its message is fit to show the operator."""

    def __init__(self, endpoint: str, cause: OSError):
        super().__init__(f"TAK server {endpoint} unreachable ({cause})")
        self.endpoint = endpoint
        self.cause = cause


class TakService:
    """Sends CoT events to the taky server over mutual TLS.

    The endpoint is read from TAK_HOST / TAK_PORT at send time, not on
    construction, so handlers can be built before `.env` is loaded.
    """

    def __init__(self, ssl_dir: Path = SSL_DIR, timeout: int = CONNECT_TIMEOUT):
        self.ssl_dir = ssl_dir
        self.timeout = timeout

    def endpoint(self) -> tuple[str, int]:
        """Host and port of the TAK server, from the environment."""
        return os.environ["TAK_HOST"], int(os.environ.get("TAK_PORT", DEFAULT_PORT))

    def _ssl_context(self) -> ssl.SSLContext:
        """Client context presenting the bot's certificate to taky.

        taky runs with `client_cert_required = True`. The bot reuses the server
        keypair as its client certificate — both are signed by the same CA.
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(self.ssl_dir / "ca.crt")
        ctx.load_cert_chain(self.ssl_dir / "server.crt", self.ssl_dir / "server.key")
        # The taky server certificate is issued for an IP, not a DNS name.
        ctx.check_hostname = False
        return ctx

    async def send(self, cot_xml: bytes) -> None:
        """Deliver one CoT event, or raise TakDeliveryError if it did not land.

        TAK over TCP gives no application-level acknowledgement, so a clean
        return means the server accepted the bytes — nothing stronger.

        Runs on a worker thread: connect and TLS handshake are blocking, and can
        take the full timeout. On the event loop that would stop the bot reading
        Signal for those seconds.
        """
        await asyncio.to_thread(self._send, cot_xml)

    def _send(self, cot_xml: bytes) -> None:
        """The blocking socket write, off the event loop."""
        host, port = self.endpoint()

        try:
            with socket.create_connection((host, port), timeout=self.timeout) as raw:
                with self._ssl_context().wrap_socket(raw) as s:
                    s.sendall(cot_xml + COT_DELIMITER)
        except OSError as e:
            logging.exception("Failed to deliver CoT to %s:%s", host, port)
            raise TakDeliveryError(f"{host}:{port}", e) from e
