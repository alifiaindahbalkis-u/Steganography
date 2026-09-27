from pathlib import Path
import sys


# =========================================================
# 1. LOKASI PROJECT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Agar folder steganography bisa ditemukan Python
sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================
# 2. IMPORT LIBRARY
# =========================================================

from PIL import Image

from steganography.enhanced_lsb import (
    enhance_lsb_plane
)


# =========================================================
# 3. FOLDER
# =========================================================

# Folder gambar cover/original
TEST_IMAGE_FOLDER = (
    PROJECT_ROOT / "test_images"
)

# Folder hasil eksperimen
RESULT_FOLDER = (
    PROJECT_ROOT
    / "experiments"
    / "results"
)

# Folder stego image
STEGO_IMAGE_FOLDER = (
    RESULT_FOLDER
    / "stego_images"
)

# Folder hasil visualisasi LSB
LSB_RESULT_FOLDER = (
    RESULT_FOLDER
    / "lsb_analysis"
)

# Buat folder jika belum ada
LSB_RESULT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# 4. EXTENSION GAMBAR
# =========================================================

SUPPORTED_EXTENSIONS = {
    ".png",
    ".bmp"
}


# =========================================================
# 5. PROSES SATU GAMBAR
# =========================================================

def process_image(
    image_path,
    output_path
):

    try:

        # Buka gambar
        image = Image.open(
            image_path
        ).convert("RGB")

        # Buat visualisasi Enhanced LSB
        lsb_image = enhance_lsb_plane(
            image
        )

        # Simpan hasil
        lsb_image.save(
            output_path,
            format="PNG"
        )

        return True

    except Exception as e:

        print(
            f"    ERROR: {e}"
        )

        return False


# =========================================================
# 6. PROSES COVER IMAGE
# =========================================================

def process_cover_images():

    print("=" * 70)
    print("ENHANCED LSB - COVER IMAGE")
    print("=" * 70)

    images = []

    for file in sorted(
        TEST_IMAGE_FOLDER.iterdir()
    ):

        if (
            file.is_file()
            and file.suffix.lower()
            in SUPPORTED_EXTENSIONS
        ):

            images.append(file)

    # Gunakan 5 gambar
    images = images[:5]

    success_count = 0

    for image_path in images:

        output_filename = (
            f"cover_"
            f"{image_path.stem.replace(' ', '_')}"
            f"_lsb.png"
        )

        output_path = (
            LSB_RESULT_FOLDER
            / output_filename
        )

        print(
            f"Memproses: {image_path.name}"
        )

        success = process_image(
            image_path,
            output_path
        )

        if success:

            success_count += 1

            print(
                f"    Berhasil -> "
                f"{output_filename}"
            )

        print()

    print(
        f"Cover berhasil: "
        f"{success_count}/{len(images)}"
    )

    print()


# =========================================================
# 7. PROSES STEGO IMAGE
# =========================================================

def process_stego_images():

    print("=" * 70)
    print("ENHANCED LSB - STEGO IMAGE")
    print("=" * 70)

    if not STEGO_IMAGE_FOLDER.exists():

        print(
            "ERROR: Folder stego_images "
            "tidak ditemukan."
        )

        return

    stego_images = []

    for file in sorted(
        STEGO_IMAGE_FOLDER.iterdir()
    ):

        if (
            file.is_file()
            and file.suffix.lower()
            in SUPPORTED_EXTENSIONS
        ):

            stego_images.append(file)

    print(
        f"Ditemukan {len(stego_images)} "
        f"stego image."
    )

    print()

    success_count = 0

    for image_path in stego_images:

        output_filename = (
            f"{image_path.stem}"
            f"_lsb.png"
        )

        output_path = (
            LSB_RESULT_FOLDER
            / output_filename
        )

        print(
            f"Memproses: {image_path.name}"
        )

        success = process_image(
            image_path,
            output_path
        )

        if success:

            success_count += 1

            print(
                f"    Berhasil -> "
                f"{output_filename}"
            )

        print()

    print(
        f"Stego berhasil: "
        f"{success_count}/{len(stego_images)}"
    )

    print()


# =========================================================
# 8. PROGRAM UTAMA
# =========================================================

def main():

    print()
    print("=" * 70)
    print("ENHANCED LSB VISUAL STEGANALYSIS")
    print("=" * 70)
    print()

    print(
        "Folder hasil:"
    )

    print(
        LSB_RESULT_FOLDER
    )

    print()

    # Proses 5 cover image
    process_cover_images()

    # Proses 15 stego image
    process_stego_images()

    print("=" * 70)
    print("PROSES SELESAI")
    print("=" * 70)

    print()

    print(
        "Hasil Enhanced LSB tersimpan di:"
    )

    print(
        LSB_RESULT_FOLDER
    )

    print()


# =========================================================
# 9. PROGRAM UTAMA
# =========================================================

if __name__ == "__main__":

    main()