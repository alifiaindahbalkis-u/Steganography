from io import BytesIO

from PIL import Image
from werkzeug.datastructures import FileStorage

from steganography.batch_encode import encode_batch_item
from steganography.encryption import decrypt_message
from steganography.mbit_lsb import decode_mbit_data


def make_png_upload():
    image = Image.new(
        "RGB",
        (96, 96),
        color=(120, 150, 200)
    )
    image_stream = BytesIO()
    image.save(image_stream, format="PNG")
    image_stream.seek(0)

    return FileStorage(
        stream=image_stream,
        filename="cover.png"
    )


def test_batch_processes_only_selected_mode_by_default():
    result = encode_batch_item(
        make_png_upload(),
        "A short secret message",
        "test-stego-key",
        2
    )

    assert result["success"] is True
    assert result["compare_all_modes"] is False
    assert [item["m"] for item in result["comparison_results"]] == [2]
    assert [item["bits_per_channel"] for item in result["mode_results"]] == [2]

    payload = decode_mbit_data(
        result["stego_image"],
        "test-stego-key",
        2
    )
    assert decrypt_message(payload, "test-stego-key") == "A short secret message"


def test_batch_can_compare_all_modes_when_requested():
    result = encode_batch_item(
        make_png_upload(),
        "A short secret message",
        "test-stego-key",
        2,
        compare_all_modes=True
    )

    assert result["success"] is True
    assert result["compare_all_modes"] is True
    assert [item["m"] for item in result["comparison_results"]] == [1, 2, 3, 4]
    assert [item["bits_per_channel"] for item in result["mode_results"]] == [1, 2, 3, 4]