import pytest

from signalbot.test_utils import ChatTestCase, mock_chat

from commands.atak import ATAKCommand, DEFAULT_COT_TYPE, coord_error, cot_type_for


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

class TestATAKChat(ChatTestCase):
    # `setup_method`, not `setup`: pytest >=8 no longer calls nose-style `setup`
    def setup_method(self, method):
        super().setup()
        self.signal_bot.register(ATAKCommand())

    @pytest.fixture(autouse=True)
    def no_transmit(self, mocker):
        # Patched before `mock_chat` runs the pipeline, so a report that should
        # have been rejected cannot quietly reach the TAK server.
        self.connect_mock = mocker.patch("commands.atak.socket.create_connection")

    @mock_chat("999.9 999.9 tank")
    async def test_out_of_range_report_is_not_transmitted(self, mocker):
        self.connect_mock.assert_not_called()

        assert self.send_mock.call_count == 1
        sent = next(iter(self.send_mock.results()))
        assert "Could not add tank" in sent.message
        assert "latitude 999.9 is outside ±90" in sent.message
