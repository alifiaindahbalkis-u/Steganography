import os
import base64
from io import BytesIO

from flask import (
    Flask,
    render_template,
    request,
    send_from_directory
)

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


# ============================================================
# KONFIGURASI APLIKASI
# ============================================================

app = Flask(__name__)


# Vercel menggunakan filesystem sementara (/tmp).
# Saat dijalankan secara lokal, gunakan folder project biasa.
if os.environ.get("VERCEL") == "1":
    UPLOAD_FOLDER = "/tmp/uploads"
    OUTPUT_FOLDER = "/tmp/outputs"
else:
    UPLOAD_FOLDER = "uploads"
    OUTPUT_FOLDER = "outputs"


ALLOWED_EXTENSIONS = {
    "png",
    "bmp"
}


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)


# ============================================================
# FUNGSI BANTU
# ============================================================

def allowed_file(filename):
    """
    Memeriksa apakah file memiliki ekstensi
    PNG atau BMP.
    """

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


def image_to_data_uri(
    image,
    image_format="PNG"
):
    """
    Mengubah PIL Image menjadi Data URI Base64.

    Digunakan agar gambar dapat langsung ditampilkan
    di browser tanpa bergantung pada filesystem Vercel.
    """

    buffer = BytesIO()

    image.save(
        buffer,
        format=image_format
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    if image_format.upper() == "JPEG":
        mime_type = "image/jpeg"
    else:
        mime_type = "image/png"

    return (
        f"data:{mime_type};base64,{encoded}"
    )


def file_to_data_uri(
    file_path,
    mime_type
):
    """
    Membaca file kemudian mengubahnya menjadi
    Data URI Base64.
    """

    with open(
        file_path,
        "rb"
    ) as file:

        encoded = base64.b64encode(
            file.read()
        ).decode("utf-8")

    return (
        f"data:{mime_type};base64,{encoded}"
    )


def file_to_base64(
    file_path
):
    """
    Mengubah file menjadi Base64 biasa.

    Digunakan untuk mengirim data JPEG ke endpoint
    /jpeg-test tanpa bergantung pada filesystem
    antar-invocation Vercel.
    """

    with open(
        file_path,
        "rb"
    ) as file:

        return base64.b64encode(
            file.read()
        ).decode("utf-8")


def base64_to_bytes(
    encoded_data
):
    """
    Mengubah Base64 kembali menjadi bytes.
    """

    return base64.b64decode(
        encoded_data
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# ENCODE
# ============================================================

@app.route(
    "/encode",
    methods=["GET", "POST"]
)
def encode():

    if request.method == "GET":

        return render_template(
            "encode.html"
        )


    # --------------------------------------------------------
    # MENGAMBIL INPUT
    # --------------------------------------------------------

    image_file = request.files.get(
        "image"
    )

    message = request.form.get(
        "message",
        ""
    )

    stego_key = request.form.get(
        "stego_key",
        ""
    )


    # --------------------------------------------------------
    # VALIDASI GAMBAR
    # --------------------------------------------------------

    if (
        not image_file
        or image_file.filename == ""
    ):

        return render_template(
            "encode.html",
            error=(
                "Silakan pilih gambar terlebih dahulu."
            )
        )


    if not allowed_file(
        image_file.filename
    ):

        return render_template(
            "encode.html",
            error=(
                "Format gambar harus PNG atau BMP."
            )
        )


    # --------------------------------------------------------
    # VALIDASI PESAN
    # --------------------------------------------------------

    if not message.strip():

        return render_template(
            "encode.html",
            error=(
                "Pesan tidak boleh kosong."
            )
        )


    # --------------------------------------------------------
    # VALIDASI STEGO-KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "encode.html",
            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    try:

        # ----------------------------------------------------
        # SIMPAN COVER IMAGE
        # ----------------------------------------------------

        filename = secure_filename(
            image_file.filename
        )

        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        image_file.save(
            input_path
        )


        # ----------------------------------------------------
        # BUKA COVER IMAGE
        # ----------------------------------------------------

        img = Image.open(
            input_path
        )


        # ----------------------------------------------------
        # PERTAHANKAN TRANSPARANSI
        # ----------------------------------------------------

        has_alpha = False
        alpha_channel = None


        if (
            img.mode in ("RGBA", "LA")
            or (
                img.mode == "P"
                and "transparency" in img.info
            )
        ):

            has_alpha = True

            img = img.convert(
                "RGBA"
            )

            alpha_channel = (
                img.getchannel("A")
            )

            # Untuk LSB, RGB tetap digunakan sebagai
            # channel penyisipan.
            #
            # Alpha tidak disentuh.
            original_image = img

        else:

            original_image = img.convert(
                "RGB"
            )


        # ----------------------------------------------------
        # HITUNG KAPASITAS
        # ----------------------------------------------------

        capacity = get_capacity(
            original_image
        )


        # ----------------------------------------------------
        # ENKRIPSI PESAN AES-GCM
        # ----------------------------------------------------

        encrypted_message = encrypt_message(
            message,
            stego_key
        )


        # ----------------------------------------------------
        # CEK KAPASITAS
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # LSB + PRNG
        # ----------------------------------------------------

        stego_image = encode_data(
            original_image,
            encrypted_message,
            stego_key
        )


        # ----------------------------------------------------
        # PASTIKAN ALPHA TETAP SAMA
        # ----------------------------------------------------

        final_output_image = stego_image


        if (
            has_alpha
            and alpha_channel is not None
        ):

            r, g, b = stego_image.convert(
                "RGB"
            ).split()

            final_output_image = Image.merge(
                "RGBA",
                (
                    r,
                    g,
                    b,
                    alpha_channel
                )
            )


        # ----------------------------------------------------
        # NAMA STEGO IMAGE
        # ----------------------------------------------------

        output_filename = (
            "stego_"
            + os.path.splitext(
                filename
            )[0]
            + ".png"
        )


        output_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            output_filename
        )


        # ----------------------------------------------------
        # SIMPAN STEGO PNG
        # ----------------------------------------------------

        final_output_image.save(
            output_path,
            format="PNG"
        )


        # ----------------------------------------------------
        # ENHANCED LSB
        # ----------------------------------------------------

        lsb_image = enhance_lsb_plane(
            final_output_image
        )


        lsb_filename = (
            "lsb_"
            + os.path.splitext(
                filename
            )[0]
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


        # ----------------------------------------------------
        # MSE
        # ----------------------------------------------------

        mse = calculate_mse(
            original_image,
            final_output_image
        )


        # ----------------------------------------------------
        # PSNR
        # ----------------------------------------------------

        psnr = calculate_psnr(
            original_image,
            final_output_image
        )


        # ----------------------------------------------------
        # HISTOGRAM COVER
        # ----------------------------------------------------

        cover_histogram = calculate_histogram(
            original_image
        )


        # ----------------------------------------------------
        # HISTOGRAM STEGO
        # ----------------------------------------------------

        stego_histogram = calculate_histogram(
            final_output_image
        )


        # ----------------------------------------------------
        # JPEG RE-SAVE TEST
        # ----------------------------------------------------

        jpeg_filename = (
            "jpeg_test_"
            + os.path.splitext(
                filename
            )[0]
            + ".jpg"
        )


        jpeg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            jpeg_filename
        )


        save_as_jpeg(
            final_output_image,
            jpeg_path,
            quality=75
        )


        # ----------------------------------------------------
        # BUAT DATA URI UNTUK BROWSER
        # ----------------------------------------------------

        cover_data_uri = image_to_data_uri(
            original_image,
            "PNG"
        )


        stego_data_uri = image_to_data_uri(
            final_output_image,
            "PNG"
        )


        lsb_data_uri = image_to_data_uri(
            lsb_image,
            "PNG"
        )


        jpeg_data_uri = file_to_data_uri(
            jpeg_path,
            "image/jpeg"
        )


        # ----------------------------------------------------
        # DATA JPEG DALAM BASE64
        # ----------------------------------------------------

        jpeg_data_base64 = file_to_base64(
            jpeg_path
        )


        # ----------------------------------------------------
        # RENDER HASIL
        # ----------------------------------------------------

        return render_template(
            "encode.html",

            success=True,

            # Nama file
            output_filename=output_filename,
            lsb_filename=lsb_filename,
            original_filename=filename,
            jpeg_filename=jpeg_filename,

            # Data ukuran
            message_length=len(
                message.encode("utf-8")
            ),

            encrypted_length=len(
                encrypted_message
            ),

            capacity=capacity,

            # Metrics
            mse=mse,
            psnr=psnr,

            # Histogram
            cover_histogram=cover_histogram,
            stego_histogram=stego_histogram,

            # Pesan asli
            original_message=message,

            # Data URI gambar
            cover_data_uri=cover_data_uri,
            stego_data_uri=stego_data_uri,
            lsb_data_uri=lsb_data_uri,
            jpeg_data_uri=jpeg_data_uri,

            # JPEG untuk endpoint test
            jpeg_data_base64=jpeg_data_base64
        )


    except Exception as e:

        return render_template(
            "encode.html",
            error=(
                f"Terjadi kesalahan: {str(e)}"
            )
        )


# ============================================================
# JPEG RE-SAVE TEST
# ============================================================

@app.route(
    "/jpeg-test",
    methods=["POST"]
)
def jpeg_test():

    # --------------------------------------------------------
    # AMBIL DATA FORM
    # --------------------------------------------------------

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

    jpeg_data_base64 = request.form.get(
        "jpeg_data_base64",
        ""
    )


    # --------------------------------------------------------
    # VALIDASI KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "jpeg_test.html",

            success=False,
            message_intact=False,

            original_message=original_message,
            extracted_message=None,

            jpeg_filename=jpeg_filename,

            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    # --------------------------------------------------------
    # VALIDASI JPEG
    # --------------------------------------------------------

    if not jpeg_data_base64:

        # Fallback untuk penggunaan lokal.
        if (
            not jpeg_filename
            or not os.path.exists(
                os.path.join(
                    app.config["OUTPUT_FOLDER"],
                    jpeg_filename
                )
            )
        ):

            return render_template(
                "jpeg_test.html",

                success=False,
                message_intact=False,

                original_message=original_message,
                extracted_message=None,

                jpeg_filename=jpeg_filename,

                error=(
                    "Data JPEG untuk pengujian "
                    "tidak ditemukan."
                )
            )


    try:

        # ----------------------------------------------------
        # BACA JPEG
        # ----------------------------------------------------

        if jpeg_data_base64:

            jpeg_bytes = base64_to_bytes(
                jpeg_data_base64
            )

            jpeg_image = Image.open(
                BytesIO(jpeg_bytes)
            ).convert("RGB")

        else:

            jpeg_path = os.path.join(
                app.config["OUTPUT_FOLDER"],
                jpeg_filename
            )

            jpeg_image = Image.open(
                jpeg_path
            ).convert("RGB")


        # ----------------------------------------------------
        # EKSTRAK DATA LSB
        # ----------------------------------------------------

        encrypted_message = decode_data(
            jpeg_image,
            stego_key
        )


        # ----------------------------------------------------
        # DEKRIPSI AES-GCM
        # ----------------------------------------------------

        extracted_message = decrypt_message(
            encrypted_message,
            stego_key
        )


        # ----------------------------------------------------
        # BANDINKAN PESAN
        # ----------------------------------------------------

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


# ============================================================
# NORMAL DECODE
# ============================================================

@app.route(
    "/decode",
    methods=["GET", "POST"]
)
def decode():

    if request.method == "GET":

        return render_template(
            "decode.html"
        )


    # --------------------------------------------------------
    # AMBIL INPUT
    # --------------------------------------------------------

    image_file = request.files.get(
        "image"
    )

    stego_key = request.form.get(
        "stego_key",
        ""
    )


    # --------------------------------------------------------
    # VALIDASI FILE
    # --------------------------------------------------------

    if (
        not image_file
        or image_file.filename == ""
    ):

        return render_template(
            "decode.html",
            error=(
                "Silakan pilih stego image "
                "terlebih dahulu."
            )
        )


    if not allowed_file(
        image_file.filename
    ):

        return render_template(
            "decode.html",
            error=(
                "Format gambar harus PNG atau BMP."
            )
        )


    # --------------------------------------------------------
    # VALIDASI STEGO-KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "decode.html",
            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    try:

        # ----------------------------------------------------
        # SIMPAN FILE
        # ----------------------------------------------------

        filename = secure_filename(
            image_file.filename
        )


        input_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )


        image_file.save(
            input_path
        )


        # ----------------------------------------------------
        # BUKA STEGO IMAGE
        # ----------------------------------------------------

        stego_image = Image.open(
            input_path
        ).convert("RGB")


        # ----------------------------------------------------
        # EKSTRAK DATA
        # ----------------------------------------------------

        encrypted_message = decode_data(
            stego_image,
            stego_key
        )


        # ----------------------------------------------------
        # DEKRIPSI
        # ----------------------------------------------------

        message = decrypt_message(
            encrypted_message,
            stego_key
        )


        # ----------------------------------------------------
        # HASIL
        # ----------------------------------------------------

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


# ============================================================
# OUTPUT FILE
# ============================================================

@app.route(
    "/outputs/<filename>"
)
def output_file(filename):

    return send_from_directory(
        app.config["OUTPUT_FOLDER"],
        filename
    )


# ============================================================
# UPLOAD FILE
# ============================================================

@app.route(
    "/uploads/<filename>"
)
def upload_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


# ============================================================
# RUN LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )