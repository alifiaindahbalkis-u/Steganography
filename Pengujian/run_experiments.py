import os
import csv
import sys

from PIL import Image

# =========================================================
# AGAR PACKAGE "steganography" BISA DITEMUKAN
# =========================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# =========================================================
# IMPORT MODUL PROJECT
# =========================================================

from steganography.encryption import encrypt_message
from steganography.lsb import encode_data, get_capacity
from steganography.metrics import calculate_mse, calculate_psnr


# =========================================================
# KONFIGURASI
# =========================================================

TEST_IMAGE_DIR = os.path.join(
    os.path.dirname(__file__),
    "test_images"
)

RESULT_DIR = os.path.join(
    os.path.dirname(__file__),
    "results"
)

STEGO_DIR = os.path.join(
    RESULT_DIR,
    "stego"
)

CSV_FILE = os.path.join(
    RESULT_DIR,
    "hasil_pengujian_psnr_mse.csv"
)

# Gunakan satu stego-key untuk seluruh pengujian
STEGO_KEY = "kunci-pengujian-2026"


# =========================================================
# 3 UKURAN PESAN
# =========================================================
#
# Kita buat pesan dalam 3 tingkat:
# - Kecil
# - Sedang
# - Besar
#
# Ukuran dihitung berdasarkan jumlah karakter.
# =========================================================

MESSAGES = {
    "Kecil": (
        "Pesan pengujian kecil untuk steganografi."
    ),

    "Sedang": (
        "Ini adalah pesan pengujian ukuran sedang. "
        "Pesan ini digunakan untuk melihat perubahan "
        "nilai MSE dan PSNR setelah data disisipkan "
        "ke dalam citra menggunakan metode LSB."
    ),

    "Besar": (
        "Ini adalah pesan pengujian ukuran besar. "
        "Pesan ini digunakan untuk menguji pengaruh "
        "jumlah data yang lebih banyak terhadap kualitas "
        "citra setelah proses steganografi. "
    ) * 10
}


# =========================================================
# FUNGSI MENCARI GAMBAR
# =========================================================

def get_test_images():
    """
    Mengambil maksimal 5 gambar PNG/BMP
    dari folder test_images.
    """

    if not os.path.exists(TEST_IMAGE_DIR):
        print("ERROR:")
        print(
            f"Folder tidak ditemukan: {TEST_IMAGE_DIR}"
        )
        return []

    files = []

    for filename in os.listdir(TEST_IMAGE_DIR):

        if filename.lower().endswith(
            (".png", ".bmp")
        ):
            files.append(filename)

    files.sort()

    return files[:5]


# =========================================================
# FUNGSI UTAMA
# =========================================================

def main():

    # -----------------------------------------------------
    # BUAT FOLDER OUTPUT
    # -----------------------------------------------------

    os.makedirs(
        RESULT_DIR,
        exist_ok=True
    )

    os.makedirs(
        STEGO_DIR,
        exist_ok=True
    )


    # -----------------------------------------------------
    # AMBIL 5 GAMBAR
    # -----------------------------------------------------

    image_files = get_test_images()


    # -----------------------------------------------------
    # VALIDASI JUMLAH GAMBAR
    # -----------------------------------------------------

    if len(image_files) < 5:

        print("=" * 60)
        print("PENGUJIAN TIDAK DAPAT DIMULAI")
        print("=" * 60)

        print(
            f"Minimal diperlukan 5 gambar PNG/BMP."
        )

        print(
            f"Gambar yang ditemukan: {len(image_files)}"
        )

        print()
        print(
            "Masukkan minimal 5 gambar ke:"
        )

        print(
            f"{TEST_IMAGE_DIR}"
        )

        return


    print("=" * 60)
    print("PENGUJIAN PSNR DAN MSE")
    print("=" * 60)

    print(
        f"Jumlah citra       : {len(image_files)}"
    )

    print(
        f"Jumlah ukuran pesan: {len(MESSAGES)}"
    )

    print(
        f"Total percobaan    : "
        f"{len(image_files) * len(MESSAGES)}"
    )

    print()


    # -----------------------------------------------------
    # MENYIMPAN HASIL
    # -----------------------------------------------------

    results = []


    # =====================================================
    # LOOP 5 CITRA
    # =====================================================

    for image_number, image_name in enumerate(
        image_files,
        start=1
    ):

        image_path = os.path.join(
            TEST_IMAGE_DIR,
            image_name
        )

        print("-" * 60)

        print(
            f"CITRA {image_number}/5: "
            f"{image_name}"
        )

        print("-" * 60)


        # -------------------------------------------------
        # BUKA COVER IMAGE
        # -------------------------------------------------

        try:

            cover_image = Image.open(
                image_path
            ).convert("RGB")

        except Exception as e:

            print(
                f"Gagal membuka gambar: {e}"
            )

            continue


        # -------------------------------------------------
        # HITUNG KAPASITAS
        # -------------------------------------------------

        try:

            capacity = get_capacity(
                cover_image
            )

        except Exception as e:

            print(
                f"Gagal menghitung kapasitas: {e}"
            )

            continue


        print(
            f"Ukuran citra       : "
            f"{cover_image.width} x "
            f"{cover_image.height}"
        )

        print(
            f"Kapasitas LSB      : "
            f"{capacity} byte"
        )

        print()


        # =================================================
        # LOOP 3 UKURAN PESAN
        # =================================================

        for message_size, message in MESSAGES.items():

            print(
                f"  Pengujian pesan: "
                f"{message_size}"
            )


            # -------------------------------------------------
            # ENKRIPSI PESAN
            # -------------------------------------------------

            try:

                encrypted_message = encrypt_message(
                    message,
                    STEGO_KEY
                )

            except Exception as e:

                print(
                    f"  Gagal enkripsi: {e}"
                )

                results.append({

                    "No": len(results) + 1,

                    "Citra": image_name,

                    "Ukuran Pesan": message_size,

                    "Panjang Pesan (karakter)": len(
                        message
                    ),

                    "Panjang Pesan (byte)": len(
                        message.encode("utf-8")
                    ),

                    "Data Terenkripsi (byte)": "-",

                    "Kapasitas (byte)": capacity,

                    "MSE": "-",

                    "PSNR (dB)": "-",

                    "Status": "Gagal Enkripsi"

                })

                continue


            encrypted_size = len(
                encrypted_message
            )


            # -------------------------------------------------
            # CEK KAPASITAS
            # -------------------------------------------------

            if encrypted_size > capacity:

                print(
                    "  STATUS: GAGAL - "
                    "pesan melebihi kapasitas"
                )

                results.append({

                    "No": len(results) + 1,

                    "Citra": image_name,

                    "Ukuran Pesan": message_size,

                    "Panjang Pesan (karakter)": len(
                        message
                    ),

                    "Panjang Pesan (byte)": len(
                        message.encode("utf-8")
                    ),

                    "Data Terenkripsi (byte)": encrypted_size,

                    "Kapasitas (byte)": capacity,

                    "MSE": "-",

                    "PSNR (dB)": "-",

                    "Status": "Melebihi Kapasitas"

                })

                continue


            # -------------------------------------------------
            # EMBEDDING LSB
            # -------------------------------------------------

            try:

                stego_image = encode_data(
                    cover_image,
                    encrypted_message,
                    STEGO_KEY
                )

            except Exception as e:

                print(
                    f"  Gagal embedding: {e}"
                )

                results.append({

                    "No": len(results) + 1,

                    "Citra": image_name,

                    "Ukuran Pesan": message_size,

                    "Panjang Pesan (karakter)": len(
                        message
                    ),

                    "Panjang Pesan (byte)": len(
                        message.encode("utf-8")
                    ),

                    "Data Terenkripsi (byte)": encrypted_size,

                    "Kapasitas (byte)": capacity,

                    "MSE": "-",

                    "PSNR (dB)": "-",

                    "Status": "Gagal Embedding"

                })

                continue


            # -------------------------------------------------
            # HITUNG MSE
            # -------------------------------------------------

            try:

                mse = calculate_mse(
                    cover_image,
                    stego_image
                )

            except Exception as e:

                print(
                    f"  Gagal menghitung MSE: {e}"
                )

                mse = None


            # -------------------------------------------------
            # HITUNG PSNR
            # -------------------------------------------------

            try:

                psnr = calculate_psnr(
                    cover_image,
                    stego_image
                )

            except Exception as e:

                print(
                    f"  Gagal menghitung PSNR: {e}"
                )

                psnr = None


            # -------------------------------------------------
            # STATUS PSNR
            # -------------------------------------------------

            if psnr is None:

                psnr_status = "Tidak dapat dihitung"

            elif psnr < 30:

                psnr_status = "Di bawah 30 dB"

            elif psnr < 40:

                psnr_status = "30-40 dB"

            else:

                psnr_status = "Di atas 40 dB"


            # -------------------------------------------------
            # SIMPAN STEGO IMAGE
            # -------------------------------------------------

            base_name = os.path.splitext(
                image_name
            )[0]

            safe_size = message_size.lower()

            output_filename = (
                f"{base_name}_"
                f"{safe_size}.png"
            )

            output_path = os.path.join(
                STEGO_DIR,
                output_filename
            )

            try:

                stego_image.save(
                    output_path,
                    format="PNG"
                )

            except Exception as e:

                print(
                    f"  Gagal menyimpan stego: {e}"
                )


            # -------------------------------------------------
            # SIMPAN DATA HASIL
            # -------------------------------------------------

            results.append({

                "No": len(results) + 1,

                "Citra": image_name,

                "Ukuran Pesan": message_size,

                "Panjang Pesan (karakter)": len(
                    message
                ),

                "Panjang Pesan (byte)": len(
                    message.encode("utf-8")
                ),

                "Data Terenkripsi (byte)": encrypted_size,

                "Kapasitas (byte)": capacity,

                "MSE": (
                    round(mse, 8)
                    if mse is not None
                    else "-"
                ),

                "PSNR (dB)": (
                    round(psnr, 4)
                    if psnr is not None
                    else "-"
                ),

                "Status": psnr_status

            })


            # -------------------------------------------------
            # TAMPILKAN HASIL
            # -------------------------------------------------

            print(
                f"  Pesan            : "
                f"{len(message)} karakter"
            )

            print(
                f"  Enkripsi         : "
                f"{encrypted_size} byte"
            )

            print(
                f"  MSE              : "
                f"{mse:.8f}"
                if mse is not None
                else
                "  MSE              : gagal"
            )

            print(
                f"  PSNR             : "
                f"{psnr:.4f} dB"
                if psnr is not None
                else
                "  PSNR             : gagal"
            )

            print(
                f"  Status           : "
                f"{psnr_status}"
            )

            print()


    # =====================================================
    # SIMPAN CSV
    # =====================================================

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        fieldnames = [

            "No",

            "Citra",

            "Ukuran Pesan",

            "Panjang Pesan (karakter)",

            "Panjang Pesan (byte)",

            "Data Terenkripsi (byte)",

            "Kapasitas (byte)",

            "MSE",

            "PSNR (dB)",

            "Status"

        ]

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            results
        )


    # =====================================================
    # RINGKASAN
    # =====================================================

    berhasil = 0
    gagal = 0

    for result in results:

        if isinstance(
            result["PSNR (dB)"],
            float
        ):

            berhasil += 1

        else:

            gagal += 1


    print()
    print("=" * 60)
    print("PENGUJIAN SELESAI")
    print("=" * 60)

    print(
        f"Total percobaan : {len(results)}"
    )

    print(
        f"Berhasil        : {berhasil}"
    )

    print(
        f"Gagal           : {gagal}"
    )

    print()

    print(
        f"CSV hasil       : {CSV_FILE}"
    )

    print(
        f"Stego images    : {STEGO_DIR}"
    )

    print("=" * 60)


# =========================================================
# PROGRAM UTAMA
# =========================================================

if __name__ == "__main__":
    main()