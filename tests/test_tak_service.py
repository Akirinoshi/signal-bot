"""Unit tests for the TAK transport — sockets and TLS are mocked out."""

from unittest.mock import MagicMock
import asyncio
import ssl
import time

import pytest

from services.tak_service import (
    COT_DELIMITER,
    DEFAULT_PORT,
    TakDeliveryError,
    TakService,
)

COT = b"<event/>"


@pytest.fixture
def service(mocker):
    """A service with the TLS context stubbed, so no certificates are needed."""
    tak = TakService()
    mocker.patch.object(tak, "_ssl_context")
    return tak


def test_endpoint_from_environment(monkeypatch):
    monkeypatch.setenv("TAK_HOST", "192.168.1.42")
    monkeypatch.setenv("TAK_PORT", "9999")

    assert TakService().endpoint() == ("192.168.1.42", 9999)


def test_endpoint_port_defaults(monkeypatch):
    monkeypatch.setenv("TAK_HOST", "192.168.1.42")
    monkeypatch.delenv("TAK_PORT", raising=False)

    assert TakService().endpoint() == ("192.168.1.42", DEFAULT_PORT)


def test_endpoint_requires_host(monkeypatch):
    monkeypatch.delenv("TAK_HOST", raising=False)

    with pytest.raises(KeyError):
        TakService().endpoint()


def test_writes_a_null_terminated_document(mocker, monkeypatch, service):
    monkeypatch.setenv("TAK_HOST", "192.168.1.42")
    monkeypatch.setenv("TAK_PORT", "8089")

    connect = mocker.patch("services.tak_service.socket.create_connection")
    wrapped = service._ssl_context.return_value.wrap_socket.return_value
    sock = wrapped.__enter__.return_value

    service._send(COT)

    assert connect.call_args.args[0] == ("192.168.1.42", 8089)
    # The delimiter is what lets the server find the message boundary.
    sock.sendall.assert_called_once_with(COT + COT_DELIMITER)


def test_raises_delivery_error_naming_the_endpoint(mocker, monkeypatch, service):
    monkeypatch.setenv("TAK_HOST", "192.168.1.42")
    monkeypatch.setenv("TAK_PORT", "8089")

    refused = ConnectionRefusedError("Connection refused")
    mocker.patch(
        "services.tak_service.socket.create_connection",
        side_effect=refused,
    )

    with pytest.raises(TakDeliveryError) as excinfo:
        service._send(COT)

    assert excinfo.value.endpoint == "192.168.1.42:8089"
    assert excinfo.value.cause is refused
    assert "192.168.1.42:8089 unreachable" in str(excinfo.value)


def test_reports_tls_failures_the_same_way(mocker, monkeypatch, service):
    monkeypatch.setenv("TAK_HOST", "192.168.1.42")

    # ssl.SSLError is an OSError, so a bad certificate is a delivery failure too.
    service._ssl_context.side_effect = ssl.SSLError("tlsv1 alert unknown ca")
    mocker.patch("services.tak_service.socket.create_connection", new=MagicMock())

    with pytest.raises(TakDeliveryError):
        service._send(COT)


async def test_send_does_not_block_the_event_loop(mocker, service):
    """A slow TAK server must not stop the bot reading Signal."""
    mocker.patch.object(service, "_send", lambda cot: time.sleep(0.2))

    ticks = 0

    async def signal_reader():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    reader = asyncio.create_task(signal_reader())
    await service.send(COT)
    reader.cancel()

    assert ticks > 0, "the event loop stalled for the whole send"


async def test_send_propagates_delivery_failure(mocker, service):
    failure = TakDeliveryError("192.168.1.42:8089", ConnectionRefusedError("refused"))
    mocker.patch.object(service, "_send", side_effect=failure)

    with pytest.raises(TakDeliveryError):
        await service.send(COT)
