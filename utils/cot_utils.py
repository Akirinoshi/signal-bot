"""Cursor on Target domain logic: target types, coordinate validation, event build.

Kept apart from the Signal handler in `commands/atak.py` so each piece is testable
on its own — no chat pipeline, no TAK server, no sockets.
"""

from datetime import datetime, timedelta
import xml.etree.ElementTree as ET


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

LAT_LIMIT = 90.0
LON_LIMIT = 180.0

# How long ATAK keeps the marker before dropping it.
STALE_AFTER = timedelta(minutes=10)


def cot_type_for(label: str) -> str:
    """CoT type for a reported target label, case-insensitive."""
    return COT_TYPES.get(label.strip().lower(), DEFAULT_COT_TYPE)


def coord_error(lat: str, lon: str) -> str | None:
    """Reason the coordinates are unusable, or None if both are in range."""
    if abs(float(lat)) > LAT_LIMIT:
        return f"latitude {lat} is outside ±{LAT_LIMIT:g}"
    if abs(float(lon)) > LON_LIMIT:
        return f"longitude {lon} is outside ±{LON_LIMIT:g}"
    return None


def _cot_time(moment: datetime) -> str:
    """ISO 8601 UTC with milliseconds and a Z suffix.

    Some TAK parsers reject second-only precision, hence the trimmed
    microseconds rather than `isoformat()`.
    """
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def build_cot(lat: str, lon: str, label: str, now: datetime) -> bytes:
    """One CoT event for a reported target, serialised for the wire.

    Coordinates are passed through as the operator typed them; validate with
    `coord_error` first. The null-byte stream delimiter belongs to the
    transport, not the document, so it is not appended here.
    """
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

        # time = when the report was generated
        # start = when the reported state became valid
        # stale = when ATAK drops the marker from the map
        "time": _cot_time(now),
        "start": _cot_time(now),
        "stale": _cot_time(now + STALE_AFTER),
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

    return ET.tostring(event, encoding="utf-8")
