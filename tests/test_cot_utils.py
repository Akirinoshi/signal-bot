"""Unit tests for the CoT helpers — no Signal pipeline, no TAK server."""

from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import pytest

from utils.cot_utils import (
    DEFAULT_COT_TYPE,
    STALE_AFTER,
    build_cot,
    coord_error,
    cot_type_for,
)

NOW = datetime(2026, 9, 1, 9, 14, 22, 481000, tzinfo=timezone.utc)


@pytest.mark.parametrize("label,expected", [
    ("tank", "a-h-G-E-V-A-T"),
    ("truck", "a-h-G-E-V-U-X"),
    ("infantry", "a-h-G-U-C-I"),
    ("Tank", "a-h-G-E-V-A-T"),          # case-insensitive
    ("submarine", DEFAULT_COT_TYPE),    # unknown label keeps the generic symbol
])
def test_cot_type_for(label, expected):
    assert cot_type_for(label) == expected


def test_distinct_targets_get_distinct_types():
    assert cot_type_for("tank") != cot_type_for("truck")


@pytest.mark.parametrize("lat,lon", [
    ("48.567123", "39.87897"),   # the sample report
    ("90", "180"),               # bounds are inclusive
    ("-90", "-180"),
    ("0", "0"),
])
def test_coords_in_range(lat, lon):
    assert coord_error(lat, lon) is None


@pytest.mark.parametrize("lat,lon,expected_field", [
    ("999.9", "999.9", "latitude"),
    ("91", "181", "latitude"),
    ("-200", "400", "latitude"),
    ("48.567123", "181", "longitude"),   # valid latitude, bad longitude
    ("48.567123", "-180.1", "longitude"),
])
def test_coords_out_of_range(lat, lon, expected_field):
    error = coord_error(lat, lon)
    assert error is not None
    assert expected_field in error


def build_event(lat="48.567123", lon="39.87897", label="tank", now=NOW):
    """Parse a built CoT event back into an element for inspection."""
    return ET.fromstring(build_cot(lat, lon, label, now))


def test_event_attributes():
    event = build_event()

    assert event.tag == "event"
    assert event.get("version") == "2.0"
    assert event.get("uid") == "tank-48.567123-39.87897"
    assert event.get("type") == "a-h-G-E-V-A-T"
    assert event.get("how") == "h-e"


def test_point_carries_coordinates_verbatim():
    point = build_event().find("point")

    # Latitude first — the reverse reading puts the sample in the Caspian Sea.
    assert point.get("lat") == "48.567123"
    assert point.get("lon") == "39.87897"

    # Altitude and error bounds are unavailable for a typed report.
    assert point.get("hae") == "9999999.0"
    assert point.get("ce") == "9999999.0"
    assert point.get("le") == "9999999.0"


def test_callsign_is_the_label():
    contact = build_event(label="truck").find("detail/contact")
    assert contact.get("callsign") == "truck"


def test_timestamps_have_millisecond_precision_and_z_suffix():
    event = build_event()

    assert event.get("time") == "2026-09-01T09:14:22.481Z"
    assert event.get("start") == event.get("time")


def test_stale_is_offset_from_the_report_time():
    event = build_event()

    parsed = datetime.strptime(event.get("stale"), "%Y-%m-%dT%H:%M:%S.%fZ")
    assert parsed.replace(tzinfo=timezone.utc) == NOW + STALE_AFTER
    assert STALE_AFTER == timedelta(minutes=10)


def test_same_report_same_uid_different_place_different_uid():
    here = build_event().get("uid")
    again = build_event(now=NOW + timedelta(minutes=1)).get("uid")
    elsewhere = build_event(lon="39.9").get("uid")

    # A re-send refreshes one marker; a new position adds a second one.
    assert here == again
    assert here != elsewhere


def test_no_stream_delimiter_in_the_document():
    # The null byte is the transport's frame marker, added by TakService.send.
    assert not build_cot("48.567123", "39.87897", "tank", NOW).endswith(b"\x00")