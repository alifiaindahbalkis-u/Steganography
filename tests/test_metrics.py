from PIL import Image

from steganography.metrics import (
    calculate_mse,
    calculate_psnr
)


def test_identical_images():
    image = Image.new(
        "RGB",
        (100, 100),
        color=(100, 100, 100)
    )

    mse = calculate_mse(
        image,
        image
    )

    psnr = calculate_psnr(
        image,
        image
    )

    assert mse == 0
    assert psnr == float("inf")


def test_different_images():
    original = Image.new(
        "RGB",
        (100, 100),
        color=(100, 100, 100)
    )

    stego = Image.new(
        "RGB",
        (100, 100),
        color=(101, 100, 100)
    )

    mse = calculate_mse(
        original,
        stego
    )

    psnr = calculate_psnr(
        original,
        stego
    )

    assert mse > 0
    assert psnr > 0


def test_different_size():
    original = Image.new(
        "RGB",
        (100, 100),
        color=(100, 100, 100)
    )

    stego = Image.new(
        "RGB",
        (200, 200),
        color=(100, 100, 100)
    )

    try:
        calculate_mse(
            original,
            stego
        )

        assert False, "Seharusnya terjadi ValueError."

    except ValueError:
        assert True