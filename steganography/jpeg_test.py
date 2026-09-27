from PIL import Image


def save_as_jpeg(
    image: Image.Image,
    output_path: str,
    quality: int = 75
) -> None:

    image = image.convert("RGB")

    image.save(
        output_path,
        format="JPEG",
        quality=quality
    )