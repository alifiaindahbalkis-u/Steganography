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
import matplotlib.pyplot as plt


# =========================================================
# 3. FOLDER
# =========================================================

# Folder gambar cover
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

# Folder hasil histogram
HISTOGRAM_RESULT_FOLDER = (
    RESULT_FOLDER
    / "histogram_analysis"
)

# Buat folder hasil jika belum ada
HISTOGRAM_RESULT_FOLDER.mkdir(
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
# 5. MENCARI COVER IMAGE
# =========================================================

def get_cover_images():

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

    return images[:5]


# =========================================================
# 6. MENGHITUNG HISTOGRAM
# =========================================================

def get_rgb_histogram(image):

    image = image.convert("RGB")

    histogram = image.histogram()

    red = histogram[0:256]
    green = histogram[256:512]
    blue = histogram[512:768]

    return red, green, blue


# =========================================================
# 7. MEMBUAT HISTOGRAM COVER VS STEGO
# =========================================================

def create_histogram(
    cover_path,
    stego_path,
    output_path
):

    # -----------------------------------------------------
    # Buka gambar
    # -----------------------------------------------------

    cover_image = Image.open(
        cover_path
    ).convert("RGB")

    stego_image = Image.open(
        stego_path
    ).convert("RGB")


    # -----------------------------------------------------
    # Ambil histogram
    # -----------------------------------------------------

    cover_red, cover_green, cover_blue = (
        get_rgb_histogram(cover_image)
    )

    stego_red, stego_green, stego_blue = (
        get_rgb_histogram(stego_image)
    )


    # -----------------------------------------------------
    # Sumbu X
    # -----------------------------------------------------

    values = range(256)


    # -----------------------------------------------------
    # Buat figure
    # -----------------------------------------------------

    plt.figure(
        figsize=(12, 6)
    )


    # -----------------------------------------------------
    # Histogram cover
    # -----------------------------------------------------

    plt.plot(
        values,
        cover_red,
        label="Cover - Red",
        linestyle="-"
    )

    plt.plot(
        values,
        cover_green,
        label="Cover - Green",
        linestyle="-"
    )

    plt.plot(
        values,
        cover_blue,
        label="Cover - Blue",
        linestyle="-"
    )


    # -----------------------------------------------------
    # Histogram stego
    # -----------------------------------------------------

    plt.plot(
        values,
        stego_red,
        label="Stego - Red",
        linestyle="--"
    )

    plt.plot(
        values,
        stego_green,
        label="Stego - Green",
        linestyle="--"
    )

    plt.plot(
        values,
        stego_blue,
        label="Stego - Blue",
        linestyle="--"
    )


    # -----------------------------------------------------
    # Judul dan label
    # -----------------------------------------------------

    plt.title(
        "Perbandingan Histogram Cover dan Stego"
    )

    plt.xlabel(
        "Nilai Intensitas Piksel"
    )

    plt.ylabel(
        "Jumlah Piksel"
    )


    # -----------------------------------------------------
    # Legend
    # -----------------------------------------------------

    plt.legend()


    # -----------------------------------------------------
    # Grid
    # -----------------------------------------------------

    plt.grid(
        True,
        alpha=0.3
    )


    # -----------------------------------------------------
    # Layout
    # -----------------------------------------------------

    plt.tight_layout()


    # -----------------------------------------------------
    # Simpan
    # -----------------------------------------------------

    plt.savefig(
        output_path,
        dpi=150
    )

    plt.close()


# =========================================================
# 8. MENJALANKAN SEMUA ANALISIS
# =========================================================

def run_histogram_analysis():

    print()
    print("=" * 70)
    print("HISTOGRAM ANALYSIS")
    print("=" * 70)
    print()


    # -----------------------------------------------------
    # Ambil 5 cover
    # -----------------------------------------------------

    cover_images = get_cover_images()

    print(
        f"Jumlah cover image: "
        f"{len(cover_images)}"
    )

    print()


    # -----------------------------------------------------
    # Cek folder stego
    # -----------------------------------------------------

    if not STEGO_IMAGE_FOLDER.exists():

        print(
            "ERROR: Folder stego_images "
            "tidak ditemukan."
        )

        return


    # -----------------------------------------------------
    # Ambil semua stego image
    # -----------------------------------------------------

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
        f"Jumlah stego image: "
        f"{len(stego_images)}"
    )

    print()


    # -----------------------------------------------------
    # Proses setiap stego image
    # -----------------------------------------------------

    success_count = 0


    for stego_path in stego_images:

        stego_name = stego_path.stem


        # -------------------------------------------------
        # Tentukan cover berdasarkan nama stego
        # -------------------------------------------------

        matched_cover = None

        for cover_path in cover_images:

            cover_name = (
                cover_path.stem
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
            )

            if stego_name.startswith(
                cover_name + "_"
            ):

                matched_cover = cover_path
                break


        # -------------------------------------------------
        # Jika cover tidak ditemukan
        # -------------------------------------------------

        if matched_cover is None:

            print(
                f"Cover tidak ditemukan untuk: "
                f"{stego_path.name}"
            )

            continue


        # -------------------------------------------------
        # Nama file histogram
        # -------------------------------------------------

        output_filename = (
            f"{stego_name}_histogram.png"
        )

        output_path = (
            HISTOGRAM_RESULT_FOLDER
            / output_filename
        )


        # -------------------------------------------------
        # Buat histogram
        # -------------------------------------------------

        print(
            f"Menganalisis: "
            f"{stego_path.name}"
        )

        print(
            f"    Cover: "
            f"{matched_cover.name}"
        )


        try:

            create_histogram(
                matched_cover,
                stego_path,
                output_path
            )

            success_count += 1

            print(
                f"    Berhasil -> "
                f"{output_filename}"
            )

        except Exception as e:

            print(
                f"    ERROR: {e}"
            )

        print()


    # =====================================================
    # RINGKASAN
    # =====================================================

    print("=" * 70)
    print("RINGKASAN HISTOGRAM")
    print("=" * 70)

    print(
        f"Total stego image : "
        f"{len(stego_images)}"
    )

    print(
        f"Berhasil          : "
        f"{success_count}"
    )

    print(
        f"Gagal             : "
        f"{len(stego_images) - success_count}"
    )

    print()

    print(
        "Hasil histogram disimpan di:"
    )

    print(
        HISTOGRAM_RESULT_FOLDER
    )

    print("=" * 70)


# =========================================================
# 9. PROGRAM UTAMA
# =========================================================

if __name__ == "__main__":

    run_histogram_analysis()