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

# Konfigurasi Aplikasi
app = Flask(__name__)

if os.environ.get("VERCEL") == "1":
    UPLOAD_FOLDER = "/tmp/uploads"
    OUTPUT_FOLDER = "/tmp/outputs"
else:
    UPLOAD_FOLDER = "uploads"
    OUTPUT_FOLDER = "outputs"

ALLOWED_EXTENSIONS = {"png", "bmp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Membuat folder untuk menyimpan file upload
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Fungsi validasi file
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )

# Section utama
@app.route("/")
def index():
    return render_template("index.html")

# Encode
@app.route("/encode", methods=["GET", "POST"])
def encode():

    if request.method == "GET":
        return render_template("encode.html")

    # Mengambil input dari pengguna
    image_file = request.files.get("image")
    message = request.form.get("message", "")
    stego_key = request.form.get("stego_key", "")

    # Validasi gambar yang diinput pengguna (PNG atau BMP)
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

    # Validasi pesan yang diinput pengguna
    if not message.strip():
        return render_template(
            "encode.html",
            error="Pesan tidak boleh kosong."
        )

    # Validasi stego Key yang diinput pengguna
    if not stego_key:
        return render_template(
            "encode.html",
            error="Stego-key tidak boleh kosong."
        )

    try:

        # Simpan cover image
        filename = secure_filename(
            image_file.filename
        )

        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image_file.save(input_path)

        # Buka cover image & hasil alpha
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

        # Hitung kapasitas maksimum data yang bisa disisipkan ke dalam cover image
        capacity = get_capacity(
            original_image
        )

        # Enkripsi pesan menggunakan AES-GCM
        encrypted_message = encrypt_message(
            message,
            stego_key
        )

        # Cek ukuran pesan terenkripsi
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

        # Sisipkan data dengan LSB + PRNG
        stego_image = encode_data(
            original_image,
            encrypted_message,
            stego_key
        )

        # Kembalikan trasnparansi (Jika ada)
        final_output_image = stego_image
        if has_alpha and alpha_channel:
            # Pisahkan RGB yang sudah disisipi pesan, gabung kembali dengan Alpha
            r, g, b = stego_image.split()
            final_output_image = Image.merge("RGBA", (r, g, b, alpha_channel))

        # Nama file stego image
        output_filename = (
            "stego_"
            + os.path.splitext(filename)[0]
            + ".png"
        )
        output_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            output_filename
        )

        # Simpan stego image sebagai PNG (Transparan)
        final_output_image.save(
            output_path,
            format="PNG"
        )

        # Enhanced LSB
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

        # Hitung MSE
        mse = calculate_mse(
            original_image,
            stego_image
        )

        # Hitung PSNR
        psnr = calculate_psnr(
            original_image,
            stego_image
        )

        # Hitung histogram cover image
        cover_histogram = calculate_histogram(
            original_image
        )

        # Hitung histogram stego image
        stego_histogram = calculate_histogram(
            stego_image
        )

        # JPEG Re-Save Test
        # Catatan: Di tahap ini, kita hanya menyimpan stego image sebagai JPEG untuk pengujian.

        jpeg_filename = (
            "jpeg_test_"
            + os.path.splitext(filename)[0]
            + ".jpg"
        )

        jpeg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            jpeg_filename
        )

        # Simpan stego image sebagai JPEG (untuk pengujian)     
        save_as_jpeg(
            stego_image,
            jpeg_path,
            quality=75
        )

        # Tampilkan hasil encode ke halaman encode.html
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

            # Data JPEG test untuk pengujian decode JPEG
            jpeg_filename=jpeg_filename,

            # Pesan asli yang dimasukkan pengguna
            # Digunakan untuk membandingkan hasil decode JPEG

            original_message=message

        )

    except Exception as e:

        return render_template(
            "encode.html",
            error=(
                f"Terjadi kesalahan: {str(e)}"
            )
        )

# Uji decode JPEG
@app.route("/jpeg-test", methods=["POST"])
def jpeg_test():

    # Ambil data dari form
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

    # VAalidasi Stego-Key
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

    # Validasi file JPEG
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

    # Lokasi file JPEG
    jpeg_path = os.path.join(
        app.config["OUTPUT_FOLDER"],
        jpeg_filename
    )

    # Cek file
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

        # Buka JPEG
        jpeg_image = Image.open(
            jpeg_path
        ).convert("RGB")

        # Extract data dari JPEG
        encrypted_message = decode_data(
            jpeg_image,
            stego_key
        )

        # Deskripsi pesan terenkripsi dengan AES-GCM
        extracted_message = decrypt_message(
            encrypted_message,
            stego_key
        )
     
        # Bandingkan dengan pesan asli
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

        # Decode gagal
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

# Decode Normal
@app.route("/decode", methods=["GET", "POST"])
def decode():

    if request.method == "GET":
        return render_template("decode.html")

    # Mengambil data dari form
    image_file = request.files.get("image")

    stego_key = request.form.get(
        "stego_key",
        ""
    )

    # Validasi file stego image
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

    # Validasi stego-key
    if not stego_key:

        return render_template(
            "decode.html",

            error=(
                "Stego-key tidak boleh kosong."
            )
        )

    try:

        # Simpan stego image
        filename = secure_filename(
            image_file.filename
        )

        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image_file.save(input_path)
       
        # Buka stego image
        stego_image = Image.open(
            input_path
        ).convert("RGB")

        # Extract data dengan LSB + PRNG
        encrypted_message = decode_data(
            stego_image,
            stego_key
        )

        # Deskripsi dengan AES-GCM
        message = decrypt_message(
            encrypted_message,
            stego_key
        )

        # tampilkan hasil decode
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

# Menampilkan output image
@app.route("/outputs/<filename>")
def output_file(filename):

    return send_from_directory(
        app.config["OUTPUT_FOLDER"],
        filename
    )

# Menampilkan cover image
@app.route("/uploads/<filename>")
def upload_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

# Menjalankan Flask
if __name__ == "__main__":

    app.run(
        debug=True
    )