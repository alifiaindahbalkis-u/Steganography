from PIL import Image

from steganography.mbit_lsb import (
    decode_mbit_data,
    encode_mbit_data,
)
from steganography.prng import (
    PositionSequence,
    generate_positions,
)


def test_same_key_same_positions():
    positions_1 = generate_positions(
        100,
        20,
        "rahasia123"
    )

    positions_2 = generate_positions(
        100,
        20,
        "rahasia123"
    )

    assert positions_1 == positions_2


def test_different_key_different_positions():
    positions_1 = generate_positions(
        100,
        20,
        "rahasia123"
    )

    positions_2 = generate_positions(
        100,
        20,
        "rahasia456"
    )

    assert positions_1 != positions_2


def test_position_count():
    positions = generate_positions(
        100,
        20,
        "rahasia123"
    )

    assert len(positions) == 20


def test_exceed_capacity():
    try:
        generate_positions(
            10,
            20,
            "rahasia123"
        )

        assert False

    except ValueError:
        assert True


def test_cached_sequence_matches_legacy_order():
    expected_prefix = generate_positions(
        1000,
        350,
        "compatibility-key"
    )
    expected_longer_prefix = generate_positions(
        1000,
        700,
        "compatibility-key"
    )
    sequence = PositionSequence(
        1000,
        "compatibility-key"
    )

    assert list(sequence.get_positions(350)) == expected_prefix
    assert list(sequence.get_positions(700)) == expected_longer_prefix
    assert list(sequence.get_positions(350)) == expected_prefix


def test_cached_mbit_encoding_matches_legacy():
    image = Image.new(
        "RGB",
        (64, 64),
        color=(120, 150, 200)
    )
    payload = b"legacy-compatible cached positions"
    key = "cache-compatibility-key"

    legacy_image = encode_mbit_data(
        image,
        payload,
        key,
        2
    )
    position_sequence = PositionSequence(
        image.width * image.height * 3,
        key
    )
    cached_image = encode_mbit_data(
        image,
        payload,
        key,
        2,
        position_sequence=position_sequence
    )

    assert list(cached_image.getdata()) == list(legacy_image.getdata())
    assert decode_mbit_data(
        cached_image,
        key,
        2,
        position_sequence=position_sequence
    ) == payload
        