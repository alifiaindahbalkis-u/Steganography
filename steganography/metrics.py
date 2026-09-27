import numpy as np
from PIL import Image


def calculate_mse(original: Image.Image, stego: Image.Image) -> float:
    original_array = np.asarray(
        original.convert("RGB"),
        dtype=np.float64
    )

    stego_array = np.asarray(
        stego.convert("RGB"),
        dtype=np.float64
    )

    if original_array.shape != stego_array.shape:
        raise ValueError(
            "Ukuran gambar original dan stego harus sama."
        )

    mse = np.mean(
        (original_array - stego_array) ** 2
    )

    return float(mse)


def calculate_psnr(original: Image.Image, stego: Image.Image) -> float:
    mse = calculate_mse(original, stego)

    if mse == 0:
        return float("inf")

    max_pixel = 255.0

    psnr = 10 * np.log10(
        (max_pixel ** 2) / mse
    )

    return float(psnr)