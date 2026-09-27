from PIL import Image

from steganography.jpeg_test import save_as_jpeg
from steganography.lsb import encode_data, decode_data


def test_save_as_jpeg(tmp_path):
    image = Image.new(
        "RGB",
        (200, 200),
        color=(120, 150, 200)
    )

    output_path = tmp_path / "test.jpg"

    save_as_jpeg(
        image,
        str(output_path),
        quality=75
    )

    assert output_path.exists()

    jpeg_image = Image.open(output_path)
    assert jpeg_image.format == "JPEG"


def test_jpeg_resave_can_break_lsb_data(tmp_path):
    image = Image.new(
        "RGB",
        (200, 200),
        color=(120, 150, 200)
    )

    payload = b"Pesan rahasia untuk pengujian JPEG"
    stego_key = "kunci-rahasia"

    # Sisipkan pesan ke gambar
    stego_image = encode_data(
        image,
        payload,
        stego_key
    )

    # Simpan ulang sebagai JPEG
    jpeg_path = tmp_path / "stego_test.jpg"

    save_as_jpeg(
        stego_image,
        str(jpeg_path),
        quality=75
    )

    jpeg_image = Image.open(jpeg_path)

    # JPEG seharusnya membuat data LSB menjadi tidak stabil.
    try:
        extracted = decode_data(
            jpeg_image,
            stego_key
        )
    except ValueError:
        extracted = None

    assert extracted != payload