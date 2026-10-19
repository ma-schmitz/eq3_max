from pathlib import Path

import pytest

from custom_components.eq3_max.protocol.messages import (
    MsgType,
    decode_ack,
    decode_frame,
    decode_pair_ping,
    decode_push_button_state,
    decode_set_temperature,
    decode_shutter_contact_state,
    decode_thermostat_state,
    decode_time_information,
    decode_wall_thermostat_control,
    decode_wall_thermostat_state,
    encode_frame,
)
from tools.mitschnitt_umwandeln import convert

FIXTURE = Path(__file__).parents[1] / "fixtures" / "mitschnitt.txt"

# Der Mitschnitt lief nur gut 1 h statt 24 h (Entscheidung des Controllers,
# siehe docs/mitschnitt.md); die Mindestzahl ist deshalb an die tatsaechliche
# Menge angepasst.
MIN_LINES = 50

SAMPLE = (
    "09/14/26 16:48:59.512 Module MAX: CUL \"My-MAX-CUL\": Info: Sending (My-MAX-CUL, WOR: yes): 0BF20540C0FFEEA1B0050149\n"
    "09/14/26 16:49:00.599 MAX packet received (My-MAX-CUL, RSSI: 0x3F): 0EF20202A1B005C0FFEE0001193009\n"
    "09/14/26 16:49:00.600 Module MAX: Info: CONTROL_MODE on channel 1 of peer 11 was set to 0x01.\n"
)


def test_convert_sample():
    assert convert(SAMPLE) == [
        "Zs0BF20540C0FFEEA1B0050149",
        "Z0EF20202A1B005C0FFEE00011930093F",
    ]


DECODERS = {
    MsgType.THERMOSTAT_STATE: decode_thermostat_state,
    MsgType.WALL_THERMOSTAT_STATE: decode_wall_thermostat_state,
    MsgType.WALL_THERMOSTAT_CONTROL: decode_wall_thermostat_control,
    MsgType.SHUTTER_CONTACT_STATE: decode_shutter_contact_state,
    MsgType.PUSH_BUTTON_STATE: decode_push_button_state,
    MsgType.PAIR_PING: decode_pair_ping,
    MsgType.ACK: decode_ack,
    MsgType.SET_TEMPERATURE: decode_set_temperature,
    MsgType.TIME_INFORMATION: decode_time_information,
}


def _lines() -> list[str]:
    return [l for l in FIXTURE.read_text().splitlines() if l and not l.startswith("#")]


@pytest.mark.skipif(not FIXTURE.exists(), reason="Mitschnitt noch nicht vorhanden")
def test_every_recorded_frame_decodes_and_roundtrips():
    lines = _lines()
    assert len(lines) > MIN_LINES
    for text in lines:
        sent = text.startswith("Zs")
        frame = decode_frame("Z" + text[2:] if sent else text)
        expected = text[2:] if sent else text[1 : 1 + 2 * (11 + len(frame.payload))]
        assert encode_frame(frame) == expected, text
        decoder = DECODERS.get(frame.msg_type)
        if decoder is not None:
            decoder(frame.payload)


@pytest.mark.skipif(not FIXTURE.exists(), reason="Mitschnitt noch nicht vorhanden")
def test_recorded_status_frames_carry_measured_temperature():
    seen = 0
    for text in _lines():
        if text.startswith("Zs"):
            continue
        frame = decode_frame(text)
        if frame.msg_type == MsgType.THERMOSTAT_STATE:
            assert decode_thermostat_state(frame.payload).measured is not None, text
            seen += 1
        elif frame.msg_type == MsgType.WALL_THERMOSTAT_STATE:
            assert decode_wall_thermostat_state(frame.payload).measured is not None, text
            seen += 1
    assert seen > 0
