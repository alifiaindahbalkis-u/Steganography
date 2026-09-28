import math
import os

from PIL import Image
from werkzeug.utils import secure_filename

from steganography.encryption import (
    decrypt_message,
    encrypt_message,
)
from steganography.histogram import calculate_histogram
from steganography.mbit_lsb import (
    decode_mbit_data,
    encode_mbit_data,
    get_mbit_capacity,
)
from steganography.metrics import calculate_mse, calculate_psnr
from steganography.enhanced_lsb import enhance_lsb_plane
from steganography.prng import PositionSequence


SUPPORTED_BITS = (1, 2, 3, 4)
ENCRYPTION_OVERHEAD_BYTES = 44


def _prepare_image(image):
    if image.mode in ("RGB", "RGBA"):
        return image

    if image.mode == "P" and "transparency" in image.info:
        return image.convert("RGBA")

    if image.mode == "LA":
        return image.convert("RGBA")

    return image.convert("RGB")


def encode_batch_item(
    image_file,
    message,
    stego_key,
    selected_bits,
    compare_all_modes=False,
):
    original_filename = secure_filename(
        os.path.basename(image_file.filename or "")
    )

    if not original_filename:
        raise ValueError("Nama file gambar tidak valid.")

    extension = os.path.splitext(original_filename)[1].lower()
    if extension not in (".png", ".bmp"):
        raise ValueError("Format gambar harus PNG atau BMP.")

    if not message or not message.strip():
        raise ValueError("Pesan rahasia tidak boleh kosong.")

    if not stego_key:
        raise ValueError("Stego-key tidak boleh kosong.")

    if selected_bits not in SUPPORTED_BITS:
        raise ValueError("Pilih satu mode LSB dari 1 sampai 4 bit.")

    image_file.stream.seek(0)
    with Image.open(image_file.stream) as opened_image:
        opened_image.load()

        original_image = _prepare_image(opened_image).copy()

    encrypted_message = encrypt_message(message, stego_key)
    encrypted_length = len(encrypted_message)
    message_length = len(message.encode("utf-8"))
    comparison_results = []
    selected_stego_image = None
    total_channels = original_image.width * original_image.height * 3
    position_sequence = PositionSequence(
        total_channels,
        stego_key,
    )

    modes_to_process = (
        SUPPORTED_BITS
        if compare_all_modes
        else (selected_bits,)
    )

    for bits in modes_to_process:
        capacity = get_mbit_capacity(original_image, bits)
        plaintext_capacity = max(
            0,
            capacity - ENCRYPTION_OVERHEAD_BYTES,
        )
        comparison = {
            "m": bits,
            "capacity": capacity,
            "plaintext_capacity": plaintext_capacity,
            "encrypted_size": encrypted_length,
            "mse": None,
            "psnr": None,
            "status": "FAIL",
            "error": "",
        }

        if encrypted_length > capacity:
            comparison["error"] = "Kapasitas tidak mencukupi."
            comparison_results.append(comparison)
            continue

        try:
            stego_candidate = encode_mbit_data(
                original_image,
                encrypted_message,
                stego_key,
                bits,
                position_sequence=position_sequence,
            )
            mse = calculate_mse(original_image, stego_candidate)
            psnr = calculate_psnr(original_image, stego_candidate)
            extracted_payload = decode_mbit_data(
                stego_candidate,
                stego_key,
                bits,
                position_sequence=position_sequence,
            )
            payload_matches = extracted_payload == encrypted_message

            if bits == selected_bits and payload_matches:
                extracted_message = decrypt_message(
                    extracted_payload,
                    stego_key,
                )
                extraction_ok = extracted_message == message
            else:
                extraction_ok = payload_matches
        except Exception:
            comparison["error"] = "Encoding atau verifikasi mode gagal."
            comparison_results.append(comparison)
            continue

        comparison["mse"] = round(mse, 6)
        comparison["psnr"] = round(psnr, 2)
        comparison["status"] = "PASS" if extraction_ok else "FAIL"

        if not extraction_ok:
            comparison["error"] = "Verifikasi ekstraksi gagal."

        if bits == selected_bits and extraction_ok:
            selected_stego_image = stego_candidate

        comparison_results.append(comparison)

    mode_results = []
    for comparison in comparison_results:
        if comparison["encrypted_size"] > comparison["capacity"]:
            mode_status = "insufficient_capacity"
        elif comparison["status"] == "PASS":
            mode_status = "pass"
        else:
            mode_status = "fail"

        mode_results.append({
            "bits_per_channel": comparison["m"],
            "capacity_bytes": comparison["capacity"],
            "plaintext_capacity_bytes": comparison["plaintext_capacity"],
            "encrypted_payload_bytes": comparison["encrypted_size"],
            "mse": (
                comparison["mse"]
                if comparison["mse"] is not None
                and math.isfinite(comparison["mse"])
                else None
            ),
            "psnr_db": (
                comparison["psnr"]
                if comparison["psnr"] is not None
                and math.isfinite(comparison["psnr"])
                else None
            ),
            "status": mode_status,
        })

    result = {
        "success": selected_stego_image is not None,
        "filename": original_filename,
        "message": message,
        "message_length": message_length,
        "encrypted_length": encrypted_length,
        "selected_m": selected_bits,
        "compare_all_modes": compare_all_modes,
        "comparison_results": comparison_results,
        "mode_results": mode_results,
        "original_image": original_image,
        "stego_image": selected_stego_image,
    }
    selected_comparison = next(
        item for item in comparison_results
        if item["m"] == selected_bits
    )
    selected_capacity = selected_comparison["capacity"]
    result.update({
        "capacity": selected_capacity,
        "plaintext_capacity": max(
            0,
            selected_capacity - ENCRYPTION_OVERHEAD_BYTES,
        ),
    })

    if selected_stego_image is None:
        result["error"] = (
            f"Mode {selected_bits}-bit tidak dapat digunakan. "
            f"{selected_comparison['error']}"
        )
        return result

    lsb_image = enhance_lsb_plane(selected_stego_image)
    jpeg_buffer_image = selected_stego_image.convert("RGB")
    cover_histogram = calculate_histogram(original_image)
    stego_histogram = calculate_histogram(selected_stego_image)
    selected_comparison = next(
        item for item in comparison_results
        if item["m"] == selected_bits
    )

    result.update({
        "capacity": selected_capacity,
        "mse": selected_comparison["mse"],
        "psnr": selected_comparison["psnr"],
        "lsb_image": lsb_image,
        "cover_histogram": cover_histogram,
        "stego_histogram": stego_histogram,
        "jpeg_image": jpeg_buffer_image,
    })

    return result