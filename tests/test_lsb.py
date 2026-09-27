from PIL import Image

from steganography.lsb import (
    bytes_to_bits,
    bits_to_bytes,
    create_header,
    parse_header,
    get_capacity,
    encode_data,
    decode_data
)


def test_bits_conversion():
    data = b"ABC123"

    bits = bytes_to_bits(data)
    result = bits_to_bytes(bits)

    assert result == data


def test_header():
    payload_length = 100

    header = create_header(payload_length)

    result = parse_header(header)

    assert result == payload_length


def test_capacity():
    image = Image.new(
        "RGB",
        (100, 100)
    )

    capacity = get_capacity(image)

    assert capacity > 0


def test_encode_decode():
    image = Image.new(
        "RGB",
        (100, 100),
        color=(120, 150, 200)
    )

    payload = b"Pesan rahasia"

    stego_image = encode_data(
        image,
        payload,
        "kunci-rahasia"
    )

    extracted = decode_data(
        stego_image,
        "kunci-rahasia"
    )

    assert extracted == payload


def test_wrong_key():
    image = Image.new(
        "RGB",
        (100, 100),
        color=(120, 150, 200)
    )

    payload = b"Pesan rahasia"

    stego_image = encode_data(
        image,
        payload,
        "kunci-benar"
    )

    try:
        decode_data(
            stego_image,
            "kunci-salah"
        )

        assert False, "Key salah seharusnya gagal."

    except ValueError:
        assert True