from pathlib import Path
import sys
import csv


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

from steganography.encryption import (
    encrypt_message,
    decrypt_message
)

from steganography.lsb import (
    encode_data,
    decode_data,
    get_capacity
)

from steganography.metrics import (
    calculate_mse,
    calculate_psnr
)


# =========================================================
# 3. FOLDER
# =========================================================

# Folder gambar pengujian
TEST_IMAGE_FOLDER = (
    PROJECT_ROOT / "test_images"
)

# Folder utama hasil eksperimen
RESULT_FOLDER = (
    PROJECT_ROOT
    / "experiments"
    / "results"
)

# Folder khusus untuk menyimpan stego image
STEGO_IMAGE_FOLDER = (
    RESULT_FOLDER
    / "stego_images"
)

# Pastikan folder hasil tersedia
RESULT_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

# Pastikan folder stego image tersedia
STEGO_IMAGE_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# 4. PENGATURAN PENGUJIAN
# =========================================================

# Kunci khusus untuk pengujian eksperimen
STEGO_KEY = "kunci-pengujian-steganografi-2026"

# Tiga kategori ukuran pesan
MESSAGE_SIZES = {
    "Kecil": 100,
    "Sedang": 1000,
    "Besar": 5000
}


# =========================================================
# 5. EXTENSION GAMBAR
# =========================================================

SUPPORTED_EXTENSIONS = {
    ".png",
    ".bmp"
}


# =========================================================
# 6. MENCARI GAMBAR PENGUJIAN
# =========================================================

def get_test_images():

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

    return images


# =========================================================
# 7. MEMBUAT PESAN UJI
# =========================================================

def generate_message(length):

    base_message = (
        "Ini adalah pesan rahasia untuk "
        "pengujian aplikasi steganografi "
        "menggunakan LSB dan AES. "
    )

    message = ""

    while len(message) < length:

        message += base_message

    return message[:length]


# =========================================================
# 8. SATU PENGUJIAN
# =========================================================

def run_single_experiment(
    image_path,
    category,
    message_length
):

    result = {
        "Gambar": image_path.name,
        "Ukuran Gambar": "",
        "Kategori Pesan": category,
        "Panjang Pesan (karakter)": message_length,
        "Pesan Terenkripsi (byte)": "",
        "Kapasitas (byte)": "",
        "MSE": "",
        "PSNR (dB)": "",
        "Encode": "GAGAL",
        "Decode": "GAGAL",
        "Pesan Sesuai": "False",
        "Status": "FAIL",
        "Keterangan": ""
    }

    try:

        # -------------------------------------------------
        # Buka gambar
        # -------------------------------------------------

        image = Image.open(
            image_path
        ).convert("RGB")

        width, height = image.size

        result["Ukuran Gambar"] = (
            f"{width} x {height}"
        )


        # -------------------------------------------------
        # Hitung kapasitas
        # -------------------------------------------------

        capacity = get_capacity(
            image
        )

        result["Kapasitas (byte)"] = (
            capacity
        )


        # -------------------------------------------------
        # Buat pesan
        # -------------------------------------------------

        message = generate_message(
            message_length
        )


        # -------------------------------------------------
        # Enkripsi AES
        # -------------------------------------------------

        encrypted_message = encrypt_message(
            message,
            STEGO_KEY
        )

        encrypted_length = len(
            encrypted_message
        )

        result[
            "Pesan Terenkripsi (byte)"
        ] = encrypted_length


        # -------------------------------------------------
        # Cek kapasitas
        # -------------------------------------------------

        if encrypted_length > capacity:

            result["Keterangan"] = (
                "Pesan terenkripsi "
                "melebihi kapasitas gambar."
            )

            return result


        # -------------------------------------------------
        # Encode
        # -------------------------------------------------

        stego_image = encode_data(
            image,
            encrypted_message,
            STEGO_KEY
        )

        result["Encode"] = "BERHASIL"


        # -------------------------------------------------
        # Simpan stego image
        # -------------------------------------------------

        # Nama gambar tanpa extension
        safe_image_name = (
            image_path.stem
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )

        # Nama kategori dibuat huruf kecil
        safe_category = category.lower()

        # Contoh:
        # download_1_kecil.png
        # download_1_sedang.png
        # download_1_besar.png

        stego_filename = (
            f"{safe_image_name}_"
            f"{safe_category}.png"
        )

        stego_path = (
            STEGO_IMAGE_FOLDER
            / stego_filename
        )

        stego_image.save(
            stego_path,
            format="PNG"
        )


        # -------------------------------------------------
        # Decode
        # -------------------------------------------------

        extracted_data = decode_data(
            stego_image,
            STEGO_KEY
        )

        result["Decode"] = "BERHASIL"


        # -------------------------------------------------
        # Dekripsi
        # -------------------------------------------------

        extracted_message = decrypt_message(
            extracted_data,
            STEGO_KEY
        )


        # -------------------------------------------------
        # Bandingkan pesan
        # -------------------------------------------------

        message_match = (
            extracted_message == message
        )

        result["Pesan Sesuai"] = str(
            message_match
        )


        # -------------------------------------------------
        # Hitung MSE
        # -------------------------------------------------

        mse = calculate_mse(
            image,
            stego_image
        )

        result["MSE"] = mse


        # -------------------------------------------------
        # Hitung PSNR
        # -------------------------------------------------

        psnr = calculate_psnr(
            image,
            stego_image
        )

        result["PSNR (dB)"] = psnr


        # -------------------------------------------------
        # Status
        # -------------------------------------------------

        if message_match:

            result["Status"] = "PASS"

            result["Keterangan"] = (
                "Encode, decode, dan "
                "verifikasi pesan berhasil."
            )

        else:

            result["Keterangan"] = (
                "Pesan hasil decode "
                "tidak sama dengan pesan asli."
            )


    except Exception as e:

        result["Keterangan"] = str(e)


    return result


# =========================================================
# 9. MENJALANKAN SEMUA PENGUJIAN
# =========================================================

def run_all_experiments():

    images = get_test_images()


    # -----------------------------------------------------
    # Cek jumlah gambar
    # -----------------------------------------------------

    if len(images) < 5:

        print(
            f"ERROR: Ditemukan {len(images)} gambar."
        )

        print(
            "Minimal diperlukan 5 gambar "
            "PNG atau BMP."
        )

        return


    # Gunakan tepat 5 gambar pertama
    images = images[:5]


    # -----------------------------------------------------
    # Informasi awal
    # -----------------------------------------------------

    print("=" * 70)
    print("PENGUJIAN STEGANOGRAFI 5 x 3")
    print("=" * 70)

    print(
        f"Jumlah gambar: {len(images)}"
    )

    print(
        "Jumlah ukuran pesan:",
        len(MESSAGE_SIZES)
    )

    print(
        "Total pengujian:",
        len(images) * len(MESSAGE_SIZES)
    )

    print()

    print(
        "Folder stego image:"
    )

    print(
        STEGO_IMAGE_FOLDER
    )

    print()


    # -----------------------------------------------------
    # Daftar hasil
    # -----------------------------------------------------

    all_results = []

    total_test = (
        len(images)
        * len(MESSAGE_SIZES)
    )

    test_number = 0


    # -----------------------------------------------------
    # Loop 5 gambar x 3 ukuran
    # -----------------------------------------------------

    for image_path in images:

        for category, message_length in (
            MESSAGE_SIZES.items()
        ):

            test_number += 1

            print(
                f"[{test_number}/{total_test}] "
                f"{image_path.name} | "
                f"{category} | "
                f"{message_length} karakter"
            )


            # Jalankan satu pengujian
            result = run_single_experiment(
                image_path,
                category,
                message_length
            )

            all_results.append(
                result
            )


            # Tampilkan hasil
            print(
                f"    Status : "
                f"{result['Status']}"
            )

            print(
                f"    Encode : "
                f"{result['Encode']}"
            )

            print(
                f"    Decode : "
                f"{result['Decode']}"
            )

            print(
                f"    Pesan sesuai : "
                f"{result['Pesan Sesuai']}"
            )

            print(
                f"    MSE : "
                f"{result['MSE']}"
            )

            print(
                f"    PSNR : "
                f"{result['PSNR (dB)']}"
            )

            if result["Keterangan"]:

                print(
                    f"    Keterangan : "
                    f"{result['Keterangan']}"
                )

            print()


    # =====================================================
    # 10. SIMPAN CSV
    # =====================================================

    csv_file = (
        RESULT_FOLDER
        / "hasil_pengujian.csv"
    )

    fieldnames = [
        "Gambar",
        "Ukuran Gambar",
        "Kategori Pesan",
        "Panjang Pesan (karakter)",
        "Pesan Terenkripsi (byte)",
        "Kapasitas (byte)",
        "MSE",
        "PSNR (dB)",
        "Encode",
        "Decode",
        "Pesan Sesuai",
        "Status",
        "Keterangan"
    ]


    with open(
        csv_file,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            all_results
        )


    # =====================================================
    # 11. RINGKASAN
    # =====================================================

    pass_count = sum(
        1
        for result in all_results
        if result["Status"] == "PASS"
    )

    fail_count = (
        len(all_results)
        - pass_count
    )


    print("=" * 70)
    print("RINGKASAN PENGUJIAN")
    print("=" * 70)

    print(
        "Total pengujian :",
        len(all_results)
    )

    print(
        "PASS             :",
        pass_count
    )

    print(
        "FAIL             :",
        fail_count
    )

    print()

    print(
        "File hasil CSV:"
    )

    print(
        csv_file
    )

    print()

    print(
        "Folder stego image:"
    )

    print(
        STEGO_IMAGE_FOLDER
    )

    print("=" * 70)


# =========================================================
# 12. PROGRAM UTAMA
# =========================================================

if __name__ == "__main__":

    run_all_experiments()