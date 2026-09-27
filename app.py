import os

from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
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

from steganography.histogram import (
    calculate_histogram
)

from steganography.enhanced_lsb import (
    enhance_lsb_plane
)

from steganography.jpeg_test import (
    save_as_jpeg
)


# =========================================================
# KONFIGURASI APLIKASI
# =========================================================

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

ALLOWED_EXTENSIONS = {"png", "bmp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER


# Membuat folder jika belum tersedia
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# =========================================================
# VALIDASI FILE
# =========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# HALAMAN UTAMA
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


# =========================================================
# ENCODE
# =========================================================

@app.route("/encode", methods=["GET", "POST"])
def encode():

    if request.method == "GET":
        return render_template("encode.html")

    # -----------------------------------------------------
    # MENGAMBIL DATA DARI FORM
    # -----------------------------------------------------

    image_file = request.files.get("image")
    message = request.form.get("message", "")
    stego_key = request.form.get("stego_key", "")

    # -----------------------------------------------------
    # VALIDASI FILE
    # -----------------------------------------------------

    if not image_file or image_file.filename == "":
        return render_template(
            "encode.html",
            error="Silakan pilih gambar terlebih dahulu."
        )

    if not allowed_file(image_file.filename):
        return render_template(
            "encode.html",
            error="Format gambar harus PNG atau BMP."
        )

    # -----------------------------------------------------
    # VALIDASI PESAN
    # -----------------------------------------------------

    if not message.strip():
        return render_template(
            "encode.html",
            error="Pesan tidak boleh kosong."
        )

    # -----------------------------------------------------
    # VALIDASI STEGO-KEY
    # -----------------------------------------------------

    if not stego_key:
        return render_template(
            "encode.html",
            error="Stego-key tidak boleh kosong."
        )

    try:

        # -------------------------------------------------
        # SIMPAN COVER IMAGE
        # -------------------------------------------------

        filename = secure_filename(
            image_file.filename
        )

        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image_file.save(input_path)

        # -------------------------------------------------
        # BUKA COVER IMAGE & SIMPAN ALPHA
        # -------------------------------------------------
        img = Image.open(input_path)
        has_alpha = False
        alpha_channel = None

        # Jika gambar transparan, simpan layer alpha-nya
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            has_alpha = True
            img = img.convert("RGBA")
            alpha_channel = img.split()[-1] 
            
            # Buat latar putih sementara sebagai wadah LSB
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=alpha_channel)
            original_image = background
        else:
            original_image = img.convert("RGB")

        # -------------------------------------------------
        # HITUNG KAPASITAS
        # -------------------------------------------------

        capacity = get_capacity(
            original_image
        )

        # -------------------------------------------------
        # ENKRIPSI PESAN DENGAN AES-GCM
        # -------------------------------------------------

        encrypted_message = encrypt_message(
            message,
            stego_key
        )

        # -------------------------------------------------
        # CEK KAPASITAS
        # -------------------------------------------------

        if len(encrypted_message) > capacity:

            return render_template(
                "encode.html",
                error=(
                    f"Pesan terlalu besar. "
                    f"Kapasitas terenkripsi gambar: "
                    f"{capacity} byte, "
                    f"sedangkan data pesan: "
                    f"{len(encrypted_message)} byte."
                )
            )

        # -------------------------------------------------
        # SISIPKAN DATA DENGAN LSB + PRNG
        # -------------------------------------------------
        stego_image = encode_data(
            original_image,
            encrypted_message,
            stego_key
        )

        # -------------------------------------------------
        # KEMBALIKAN TRANSPARANSI (JIKA ADA)
        # -------------------------------------------------
        final_output_image = stego_image
        if has_alpha and alpha_channel:
            # Pisahkan RGB yang sudah disisipi pesan, gabung kembali dengan Alpha
            r, g, b = stego_image.split()
            final_output_image = Image.merge("RGBA", (r, g, b, alpha_channel))

        # -------------------------------------------------
        # NAMA FILE STEGO
        # -------------------------------------------------
        output_filename = (
            "stego_"
            + os.path.splitext(filename)[0]
            + ".png"
        )
        output_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            output_filename
        )

        # -------------------------------------------------
        # SIMPAN STEGO IMAGE SEBAGAI PNG (TRANSPARAN)
        # -------------------------------------------------
        final_output_image.save(
            output_path,
            format="PNG"
        )

        # -------------------------------------------------
        # ENHANCED LSB
        # -------------------------------------------------

        lsb_image = enhance_lsb_plane(
            stego_image
        )

        lsb_filename = (
            "lsb_"
            + os.path.splitext(filename)[0]
            + ".png"
        )

        lsb_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            lsb_filename
        )

        lsb_image.save(
            lsb_path,
            format="PNG"
        )

        # -------------------------------------------------
        # HITUNG MSE
        # -------------------------------------------------

        mse = calculate_mse(
            original_image,
            stego_image
        )

        # -------------------------------------------------
        # HITUNG PSNR
        # -------------------------------------------------

        psnr = calculate_psnr(
            original_image,
            stego_image
        )

        # -------------------------------------------------
        # HITUNG HISTOGRAM COVER
        # -------------------------------------------------

        cover_histogram = calculate_histogram(
            original_image
        )

        # -------------------------------------------------
        # HITUNG HISTOGRAM STEGO
        # -------------------------------------------------

        stego_histogram = calculate_histogram(
            stego_image
        )

        # =================================================
        # JPEG RE-SAVE TEST
        # =================================================
        #
        # PENTING:
        # Di tahap ini JPEG hanya dibuat.
        # TIDAK ADA proses decode.
        #
        # Decode JPEG baru dilakukan setelah user
        # memasukkan stego-key di halaman encode.html.
        # =================================================

        jpeg_filename = (
            "jpeg_test_"
            + os.path.splitext(filename)[0]
            + ".jpg"
        )

        jpeg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            jpeg_filename
        )

        # -------------------------------------------------
        # SIMPAN STEGO IMAGE SEBAGAI JPEG
        # -------------------------------------------------

        save_as_jpeg(
            stego_image,
            jpeg_path,
            quality=75
        )

        # -------------------------------------------------
        # TAMPILKAN HASIL ENCODE
        # -------------------------------------------------

        return render_template(
            "encode.html",

            success=True,

            output_filename=output_filename,

            lsb_filename=lsb_filename,

            original_filename=filename,

            message_length=len(
                message.encode("utf-8")
            ),

            encrypted_length=len(
                encrypted_message
            ),

            capacity=capacity,

            mse=mse,

            psnr=psnr,

            cover_histogram=cover_histogram,

            stego_histogram=stego_histogram,

            # -------------------------------------------------
            # DATA JPEG TEST
            # -------------------------------------------------

            jpeg_filename=jpeg_filename,

            # -------------------------------------------------
            # PESAN ASLI
            # Digunakan untuk membandingkan hasil decode JPEG
            # -------------------------------------------------

            original_message=message

        )

    except Exception as e:

        return render_template(
            "encode.html",
            error=(
                f"Terjadi kesalahan: {str(e)}"
            )
        )


# =========================================================
# UJI DECODE JPEG
# =========================================================

@app.route("/jpeg-test", methods=["POST"])
def jpeg_test():

    # -----------------------------------------------------
    # AMBIL DATA DARI FORM
    # -----------------------------------------------------

    jpeg_filename = request.form.get(
        "jpeg_filename",
        ""
    )

    stego_key = request.form.get(
        "stego_key",
        ""
    )

    original_message = request.form.get(
        "original_message",
        ""
    )

    # -----------------------------------------------------
    # VALIDASI STEGO-KEY
    # -----------------------------------------------------

    if not stego_key:

        return render_template(
            "jpeg_test.html",

            success=False,

            message_intact=False,

            original_message=original_message,

            extracted_message=None,

            jpeg_filename=jpeg_filename,

            error="Stego-key tidak boleh kosong."
        )

    # -----------------------------------------------------
    # VALIDASI FILE JPEG
    # -----------------------------------------------------

    if not jpeg_filename:

        return render_template(
            "jpeg_test.html",

            success=False,

            message_intact=False,

            original_message=original_message,

            extracted_message=None,

            jpeg_filename=None,

            error=(
                "File JPEG untuk pengujian "
                "tidak ditemukan."
            )
        )

    # -----------------------------------------------------
    # LOKASI FILE JPEG
    # -----------------------------------------------------

    jpeg_path = os.path.join(
        app.config["OUTPUT_FOLDER"],
        jpeg_filename
    )

    # -----------------------------------------------------
    # CEK FILE
    # -----------------------------------------------------

    if not os.path.exists(jpeg_path):

        return render_template(
            "jpeg_test.html",

            success=False,

            message_intact=False,

            original_message=original_message,

            extracted_message=None,

            jpeg_filename=None,

            error=(
                "File JPEG tidak ditemukan."
            )
        )

    try:

        # -------------------------------------------------
        # BUKA JPEG
        # -------------------------------------------------

        jpeg_image = Image.open(
            jpeg_path
        ).convert("RGB")

        # -------------------------------------------------
        # EXTRACT DATA DARI JPEG
        # -------------------------------------------------

        encrypted_message = decode_data(
            jpeg_image,
            stego_key
        )

        # -------------------------------------------------
        # DEKRIPSI PESAN
        # -------------------------------------------------

        extracted_message = decrypt_message(
            encrypted_message,
            stego_key
        )

        # -------------------------------------------------
        # BANDINGKAN DENGAN PESAN ASLI
        # -------------------------------------------------

        if extracted_message == original_message:

            return render_template(
                "jpeg_test.html",

                success=True,

                message_intact=True,

                original_message=original_message,

                extracted_message=extracted_message,

                jpeg_filename=jpeg_filename,

                error=None
            )

        else:

            return render_template(
                "jpeg_test.html",

                success=True,

                message_intact=False,

                original_message=original_message,

                extracted_message=extracted_message,

                jpeg_filename=jpeg_filename,

                error=(
                    "Pesan berhasil diekstrak, "
                    "tetapi isinya berbeda "
                    "dengan pesan asli."
                )
            )

    except Exception as e:

        # -------------------------------------------------
        # DECODE GAGAL
        # -------------------------------------------------

        return render_template(
            "jpeg_test.html",

            success=False,

            message_intact=False,

            original_message=original_message,

            extracted_message=None,

            jpeg_filename=jpeg_filename,

            error=(
                f"Decode JPEG gagal: {str(e)}"
            )
        )


# =========================================================
# DECODE NORMAL
# =========================================================

@app.route("/decode", methods=["GET", "POST"])
def decode():

    if request.method == "GET":
        return render_template("decode.html")

    # -----------------------------------------------------
    # MENGAMBIL DATA DARI FORM
    # -----------------------------------------------------

    image_file = request.files.get("image")

    stego_key = request.form.get(
        "stego_key",
        ""
    )

    # -----------------------------------------------------
    # VALIDASI FILE
    # -----------------------------------------------------

    if not image_file or image_file.filename == "":

        return render_template(
            "decode.html",

            error=(
                "Silakan pilih stego image "
                "terlebih dahulu."
            )
        )

    if not allowed_file(image_file.filename):

        return render_template(
            "decode.html",

            error=(
                "Format gambar harus PNG atau BMP."
            )
        )

    # -----------------------------------------------------
    # VALIDASI STEGO-KEY
    # -----------------------------------------------------

    if not stego_key:

        return render_template(
            "decode.html",

            error=(
                "Stego-key tidak boleh kosong."
            )
        )

    try:

        # -------------------------------------------------
        # SIMPAN STEGO IMAGE
        # -------------------------------------------------

        filename = secure_filename(
            image_file.filename
        )

        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image_file.save(input_path)

        # -------------------------------------------------
        # BUKA STEGO IMAGE
        # -------------------------------------------------

        stego_image = Image.open(
            input_path
        ).convert("RGB")

        # -------------------------------------------------
        # EXTRACT DATA DENGAN LSB + PRNG
        # -------------------------------------------------

        encrypted_message = decode_data(
            stego_image,
            stego_key
        )

        # -------------------------------------------------
        # DEKRIPSI DENGAN AES-GCM
        # -------------------------------------------------

        message = decrypt_message(
            encrypted_message,
            stego_key
        )

        # -------------------------------------------------
        # TAMPILKAN HASIL DECODE
        # -------------------------------------------------

        return render_template(
            "decode.html",

            success=True,

            message=message,

            filename=filename
        )

    except Exception as e:

        return render_template(
            "decode.html",

            error=(
                f"Gagal melakukan decode: "
                f"{str(e)}"
            )
        )


# =========================================================
# MENAMPILKAN OUTPUT IMAGE
# =========================================================

@app.route("/outputs/<filename>")
def output_file(filename):

    return send_from_directory(
        app.config["OUTPUT_FOLDER"],
        filename
    )


# =========================================================
# MENAMPILKAN COVER IMAGE
# =========================================================

@app.route("/uploads/<filename>")
def upload_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# =========================================================
# MENJALANKAN FLASK
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )