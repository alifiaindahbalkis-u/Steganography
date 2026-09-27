from PIL import Image


def calculate_histogram(image: Image.Image) -> dict:
    """
    Menghitung histogram pixel untuk channel
    Red, Green, dan Blue.
    """

    image = image.convert("RGB")

    histogram = image.histogram()

    return {
        "red": histogram[0:256],
        "green": histogram[256:512],
        "blue": histogram[512:768]
    }