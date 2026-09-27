from steganography.prng import generate_positions


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
        