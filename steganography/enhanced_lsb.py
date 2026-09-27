from PIL import Image


def extract_lsb_plane(image: Image.Image) -> Image.Image:
    """
    Mengambil bit LSB dari setiap channel RGB
    dan mengubahnya menjadi gambar grayscale.

    LSB 0 = hitam
    LSB 1 = putih
    """

    image = image.convert("RGB")

    width, height = image.size

    output = Image.new(
        "L",
        (width, height)
    )

    output_pixels = []

    for pixel in image.getdata():

        r, g, b = pixel

        r_lsb = r & 1
        g_lsb = g & 1
        b_lsb = b & 1

        if r_lsb or g_lsb or b_lsb:
            value = 255
        else:
            value = 0

        output_pixels.append(value)

    output.putdata(output_pixels)

    return output


def enhance_lsb_plane(image: Image.Image) -> Image.Image:
    """
    Menghasilkan visualisasi Enhanced LSB
    dari gambar stego.
    """

    lsb_image = extract_lsb_plane(image)

    enhanced = lsb_image.point(
        lambda pixel: 255 if pixel > 0 else 0
    )

    return enhanced