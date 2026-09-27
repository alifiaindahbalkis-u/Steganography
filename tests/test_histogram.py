from PIL import Image

from steganography.histogram import calculate_histogram


def test_histogram_channels():

    image = Image.new(
        "RGB",
        (100, 100),
        color=(100, 150, 200)
    )

    histogram = calculate_histogram(image)

    assert "red" in histogram
    assert "green" in histogram
    assert "blue" in histogram

    assert len(histogram["red"]) == 256
    assert len(histogram["green"]) == 256
    assert len(histogram["blue"]) == 256


def test_histogram_pixel_count():

    image = Image.new(
        "RGB",
        (100, 100),
        color=(100, 150, 200)
    )

    histogram = calculate_histogram(image)

    assert sum(histogram["red"]) == 10000
    assert sum(histogram["green"]) == 10000
    assert sum(histogram["blue"]) == 10000