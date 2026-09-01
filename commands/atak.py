from signalbot import DataMessageContext, DataMessageHandler, SendMessage, regex_triggered
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
import logging
import os
import socket, ssl

# Resolved from this file, not the working directory, so the bot can be started
# from anywhere. commands/atak.py -> project root -> taky-server/ssl
SSL_DIR = Path(__file__).resolve().parent.parent / "taky-server" / "ssl"


#   a-h-G-E-V-A-T   Gnd/Equip/Vehic/Armor/Tank
#   a-h-G-E-V-U-X   Gnd/Equip/Vehic/Cross Country Truck
#   a-h-G-E-V-U-B   Gnd/Equip/Vehic/Bus
#   a-h-G-E-V-U     Gnd/Equip/Vehic/Utility
#   a-h-G-U-C-I     Gnd/Combat/Infantry/Troops (Open)
COT_TYPES = {
    "tank": "a-h-G-E-V-A-T",
    "truck": "a-h-G-E-V-U-X",
    "bus": "a-h-G-E-V-U-B",
    "vehicle": "a-h-G-E-V-U",
    "car": "a-h-G-E-V-U",
    "infantry": "a-h-G-U-C-I",
    "troops": "a-h-G-U-C-I",
}

# Unrecognized label: hostile ground, affiliation and domain only
DEFAULT_COT_TYPE = "a-h-G"


def cot_type_for(label: str) -> str:
    """CoT type for a reported target label, case-insensitive."""
    return COT_TYPES.get(label.strip().lower(), DEFAULT_COT_TYPE)


LAT_LIMIT = 90.0
LON_LIMIT = 180.0


def coord_error(lat: str, lon: str) -> str | None:
    """Reason the coordinates are unusable, or None if both are in range."""
    if abs(float(lat)) > LAT_LIMIT:
        return f"latitude {lat} is outside ±{LAT_LIMIT:g}"
    if abs(float(lon)) > LON_LIMIT:
        return f"longitude {lon} is outside ±{LON_LIMIT:g}"
    return None


class ATAKCommand(DataMessageHandler):
    COORD_RE = r"^\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\S+)\s*$"

    @regex_triggered(COORD_RE)
    async def handle_data_message(self, c: DataMessageContext):
        lat, lon, label = c.message.text.split()

        error = coord_error(lat, lon)
        if error:
            await c.send(SendMessage(
                text=f"Could not add {label} to the map — {error}. "
                     f"Expected: <latitude ±90> <longitude ±180> <label>, "
                     f"e.g. 48.567123 39.87897 tank"
            ))
            return

        now = datetime.now(timezone.utc)

        event = ET.Element("event", {
            "version": "2.0",

            # Unique object ID. Same uid = ATAK updates the existing marker,
            # new uid = new marker. Derived from label + coordinates, so two
            # "tank" reports at different places stay two markers, and a
            # re-send of the same report refreshes one marker in place.
            "uid": f"{label}-{lat}-{lon}",

            "type": cot_type_for(label),

            # h-e = human entered. The report is typed by an operator in Signal,
            # not produced by a sensor; ATAK uses this to weigh confidence.
            "how": "h-e",

            # ISO 8601 UTC with milliseconds and Z — some TAK parsers require ms.
            # time = when the report was generated
            # start = when the reported state became valid
            # stale = when ATAK drops the marker from the map
            "time": now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "start": now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "stale": (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        })

        ET.SubElement(event, "point", {
            # Task labels the example as (longitude, latitude), but in that order
            # 48.567/39.879 lands in the Caspian Sea — lat 48.567 / lon 39.879 is
            # eastern Ukraine. Parsed as lat-first.
            "lat": lat,
            "lon": lon,

            # 9999999.0 is the CoT convention for "not available". A hand-entered
            # report carries no altitude and no known error bounds, so we say so
            # rather than asserting hae=0 (which claims ellipsoid height).
            "hae": "9999999.0",  # height above ellipsoid, meters
            "ce": "9999999.0",  # circular error — horizontal accuracy, meters
            "le": "9999999.0",  # linear error — vertical accuracy, meters
        })

        detail = ET.SubElement(event, "detail")

        ET.SubElement(detail, "contact", {
            # Marker label shown in ATAK.
            "callsign": label,
        })

        cot_xml = ET.tostring(event, encoding="utf-8")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(SSL_DIR / "ca.crt")
        ctx.load_cert_chain(SSL_DIR / "server.crt", SSL_DIR / "server.key")
        # The taky server certificate is issued for an IP, not a DNS name.
        ctx.check_hostname = False

        host = os.environ["TAK_HOST"]
        port = int(os.environ.get("TAK_PORT", 8089))

        try:
            with socket.create_connection((host, port), timeout=5) as raw:
                with ctx.wrap_socket(raw) as s:
                    s.sendall(cot_xml + b"\x00")
        except OSError as e:
            logging.exception("Failed to deliver CoT for %r to %s:%s", label, host, port)
            await c.send(SendMessage(
                text=f"Could not add {label} to the map — TAK server {host}:{port} unreachable ({e})."
            ))
            return

        await c.send(SendMessage(
            text=f"Added {label} to the map at {lat}, {lon}"
        ))