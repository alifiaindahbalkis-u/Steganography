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
    get_capacity
)

from steganography.mbit_lsb import (
    encode_mbit_data,
    decode_mbit_data,
    get_mbit_capacity
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


# Vercel menggunakan filesystem sementara /tmp.
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
# FUNGSI VALIDASI
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


def validate_m_bit(value):

    try:

        m = int(value)

    except (TypeError, ValueError):

        raise ValueError(
            "Jumlah bit harus berupa 1, 2, 3, atau 4."
        )

    if m not in (
        1,
        2,
        3,
        4
    ):

        raise ValueError(
            "Jumlah bit harus berupa 1, 2, 3, atau 4."
        )

    return m


# ============================================================
# PREPARE IMAGE
# ============================================================

def prepare_image(image):
    """
    Mempertahankan transparansi jika gambar
    memiliki channel alpha.
    """

    if image.mode in (
        "RGB",
        "RGBA"
    ):

        return image


    if (
        image.mode == "P"
        and "transparency"
        in image.info
    ):

        return image.convert(
            "RGBA"
        )


    if image.mode == "LA":

        return image.convert(
            "RGBA"
        )


    return image.convert(
        "RGB"
    )


# ============================================================
# IMAGE -> BASE64 DATA URI
# ============================================================

def image_to_data_uri(
    image,
    image_format="PNG"
):
    """
    Mengubah PIL Image menjadi Base64 Data URI.

    Digunakan agar gambar dapat langsung ditampilkan
    pada browser, termasuk ketika aplikasi dijalankan
    di Vercel.
    """

    buffer = BytesIO()


    image.save(
        buffer,
        format=image_format
    )


    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode(
        "utf-8"
    )


    if image_format.upper() == "JPEG":

        mime_type = "image/jpeg"

    else:

        mime_type = "image/png"


    return (
        f"data:{mime_type};base64,{encoded}"
    )


# ============================================================
# FILE -> BASE64 DATA URI
# ============================================================

def file_to_data_uri(
    file_path,
    mime_type
):

    with open(
        file_path,
        "rb"
    ) as file:

        encoded = base64.b64encode(
            file.read()
        ).decode(
            "utf-8"
        )


    return (
        f"data:{mime_type};base64,{encoded}"
    )


# ============================================================
# FILE -> BASE64
# ============================================================

def file_to_base64(
    file_path
):

    with open(
        file_path,
        "rb"
    ) as file:

        return base64.b64encode(
            file.read()
        ).decode(
            "utf-8"
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
    methods=[
        "GET",
        "POST"
    ]
)
def encode():

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "encode.html"
        )


    # --------------------------------------------------------
    # AMBIL INPUT
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


    selected_m_value = request.form.get(
        "lsb_bits",
        "1"
    )


    # --------------------------------------------------------
    # VALIDASI JUMLAH BIT
    # --------------------------------------------------------

    try:

        selected_m = validate_m_bit(
            selected_m_value
        )

    except ValueError as e:

        return render_template(
            "encode.html",
            error=str(e)
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
    # VALIDASI STEGO KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "encode.html",
            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    try:

        # ====================================================
        # SIMPAN COVER IMAGE
        # ====================================================

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


        # ====================================================
        # BUKA COVER IMAGE
        # ====================================================

        original_image = Image.open(
            input_path
        )


        original_image = prepare_image(
            original_image
        )


        # ====================================================
        # COVER DATA URI
        # ====================================================

        cover_data_uri = image_to_data_uri(
            original_image,
            "PNG"
        )


        # ====================================================
        # ENKRIPSI PESAN
        # ====================================================
        #
        # Pesan dienkripsi SATU KALI.
        #
        # Payload terenkripsi yang sama digunakan untuk
        # perbandingan 1-bit, 2-bit, 3-bit, dan 4-bit.
        #
        # ====================================================

        encrypted_message = encrypt_message(
            message,
            stego_key
        )


        encrypted_length = len(
            encrypted_message
        )


        message_length = len(
            message.encode(
                "utf-8"
            )
        )


        # ====================================================
        # OVERHEAD AES-GCM
        # ====================================================
        #
        # Salt       = 16 byte
        # Nonce      = 12 byte
        # GCM tag    = 16 byte
        #
        # Total      = 44 byte
        #
        # ====================================================

        encryption_overhead = 44


        # ====================================================
        # PERBANDINGAN 1-4 BIT
        # ====================================================

        comparison_results = []


        selected_stego_image = None


        # ====================================================
        # UJI m = 1, 2, 3, 4
        # ====================================================

        for m in (
            1,
            2,
            3,
            4
        ):

            # ------------------------------------------------
            # HITUNG KAPASITAS
            # ------------------------------------------------

            capacity = get_mbit_capacity(
                original_image,
                m
            )


            # ------------------------------------------------
            # KAPASITAS PESAN ASLI
            # ------------------------------------------------

            plaintext_capacity = max(
                0,
                capacity
                - encryption_overhead
            )


            # ------------------------------------------------
            # DATA HASIL
            # ------------------------------------------------

            result = {

                "m":
                    m,

                "capacity":
                    capacity,

                "plaintext_capacity":
                    plaintext_capacity,

                "encrypted_size":
                    encrypted_length,

                "mse":
                    None,

                "psnr":
                    None,

                "status":
                    "FAIL",

                "error":
                    ""

            }


            # ------------------------------------------------
            # CEK KAPASITAS
            # ------------------------------------------------

            if encrypted_length > capacity:

                result["error"] = (
                    "Kapasitas tidak mencukupi."
                )


                comparison_results.append(
                    result
                )


                continue


            # ------------------------------------------------
            # ENCODE m-BIT
            # ------------------------------------------------

            stego_candidate = encode_mbit_data(
                original_image,
                encrypted_message,
                stego_key,
                m
            )


            # ------------------------------------------------
            # MSE
            # ------------------------------------------------

            mse = calculate_mse(
                original_image,
                stego_candidate
            )


            # ------------------------------------------------
            # PSNR
            # ------------------------------------------------

            psnr = calculate_psnr(
                original_image,
                stego_candidate
            )


            # ------------------------------------------------
            # VERIFIKASI DECODE
            # ------------------------------------------------

            try:

                extracted_encrypted = (
                    decode_mbit_data(
                        stego_candidate,
                        stego_key,
                        m
                    )
                )


                extracted_message = (
                    decrypt_message(
                        extracted_encrypted,
                        stego_key
                    )
                )


                extraction_ok = (
                    extracted_message
                    == message
                )


            except Exception:

                extraction_ok = False


            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            if extraction_ok:

                result["status"] = (
                    "PASS"
                )

            else:

                result["status"] = (
                    "FAIL"
                )

                result["error"] = (
                    "Verifikasi ekstraksi gagal."
                )


            # ------------------------------------------------
            # SIMPAN MSE DAN PSNR
            # ------------------------------------------------

            result["mse"] = round(
                mse,
                6
            )


            result["psnr"] = round(
                psnr,
                2
            )


            comparison_results.append(
                result
            )


            # ------------------------------------------------
            # SIMPAN STEGO MODE TERPILIH
            # ------------------------------------------------

            if (
                m == selected_m
                and extraction_ok
            ):

                selected_stego_image = (
                    stego_candidate
                )


        # ====================================================
        # VALIDASI MODE YANG DIPILIH
        # ====================================================

        if selected_stego_image is None:

            selected_result = next(
                (
                    item
                    for item in comparison_results
                    if item["m"]
                    == selected_m
                ),
                None
            )


            if selected_result:

                error_message = (
                    f"Mode {selected_m}-bit "
                    f"tidak dapat digunakan. "
                    f"{selected_result.get('error', '')}"
                )

            else:

                error_message = (
                    f"Mode {selected_m}-bit gagal."
                )


            return render_template(
                "encode.html",

                error=error_message,

                comparison_results=
                    comparison_results,

                selected_m=
                    selected_m
            )


        # ====================================================
        # NAMA FILE STEGO
        # ====================================================

        output_filename = (
            "stego_"
            + os.path.splitext(
                filename
            )[0]
            + "_"
            + str(selected_m)
            + "bit.png"
        )


        output_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            output_filename
        )


        # ====================================================
        # SIMPAN STEGO IMAGE
        # ====================================================

        selected_stego_image.save(
            output_path,
            format="PNG"
        )


        # ====================================================
        # ENHANCED LSB
        # ====================================================

        lsb_image = enhance_lsb_plane(
            selected_stego_image
        )


        lsb_filename = (
            "lsb_"
            + os.path.splitext(
                filename
            )[0]
            + "_"
            + str(selected_m)
            + "bit.png"
        )


        lsb_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            lsb_filename
        )


        lsb_image.save(
            lsb_path,
            format="PNG"
        )


        # ====================================================
        # MSE MODE TERPILIH
        # ====================================================

        mse = calculate_mse(
            original_image,
            selected_stego_image
        )


        # ====================================================
        # PSNR MODE TERPILIH
        # ====================================================

        psnr = calculate_psnr(
            original_image,
            selected_stego_image
        )


        # ====================================================
        # HISTOGRAM
        # ====================================================

        cover_histogram = calculate_histogram(
            original_image
        )


        stego_histogram = calculate_histogram(
            selected_stego_image
        )


        # ====================================================
        # JPEG RE-SAVE
        # ====================================================

        jpeg_filename = (
            "jpeg_test_"
            + os.path.splitext(
                filename
            )[0]
            + "_"
            + str(selected_m)
            + "bit.jpg"
        )


        jpeg_path = os.path.join(
            app.config["OUTPUT_FOLDER"],
            jpeg_filename
        )


        save_as_jpeg(
            selected_stego_image,
            jpeg_path,
            quality=75
        )


        # ====================================================
        # BASE64 DATA URI
        # ====================================================

        stego_data_uri = image_to_data_uri(
            selected_stego_image,
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


        jpeg_data_base64 = file_to_base64(
            jpeg_path
        )


        # ====================================================
        # KAPASITAS MODE TERPILIH
        # ====================================================

        selected_capacity = get_mbit_capacity(
            original_image,
            selected_m
        )


        selected_plaintext_capacity = max(
            0,
            selected_capacity
            - encryption_overhead
        )


        # ====================================================
        # RENDER HALAMAN
        # ====================================================

        return render_template(

            "encode.html",


            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            success=True,


            # ------------------------------------------------
            # FILE NAME
            # ------------------------------------------------

            original_filename=
                filename,

            output_filename=
                output_filename,

            lsb_filename=
                lsb_filename,

            jpeg_filename=
                jpeg_filename,


            # ------------------------------------------------
            # MODE
            # ------------------------------------------------

            selected_m=
                selected_m,


            # ------------------------------------------------
            # MESSAGE
            # ------------------------------------------------

            message_length=
                message_length,

            encrypted_length=
                encrypted_length,


            # ------------------------------------------------
            # CAPACITY
            # ------------------------------------------------

            capacity=
                selected_capacity,

            plaintext_capacity=
                selected_plaintext_capacity,


            # ------------------------------------------------
            # MSE / PSNR
            # ------------------------------------------------

            mse=
                mse,

            psnr=
                psnr,


            # ------------------------------------------------
            # HISTOGRAM
            # ------------------------------------------------

            cover_histogram=
                cover_histogram,

            stego_histogram=
                stego_histogram,


            # ------------------------------------------------
            # ORIGINAL MESSAGE
            # ------------------------------------------------

            original_message=
                message,


            # ------------------------------------------------
            # IMAGE DATA
            # ------------------------------------------------

            cover_data_uri=
                cover_data_uri,

            stego_data_uri=
                stego_data_uri,

            lsb_data_uri=
                lsb_data_uri,

            jpeg_data_uri=
                jpeg_data_uri,


            # ------------------------------------------------
            # JPEG DATA
            # ------------------------------------------------

            jpeg_data_base64=
                jpeg_data_base64,


            # ------------------------------------------------
            # COMPARISON 1-4 BIT
            # ------------------------------------------------

            comparison_results=
                comparison_results,


            error=None

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
    # AMBIL DATA
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


    lsb_bits_value = request.form.get(
        "lsb_bits",
        "1"
    )


    # --------------------------------------------------------
    # VALIDASI M-BIT
    # --------------------------------------------------------

    try:

        lsb_bits = validate_m_bit(
            lsb_bits_value
        )

    except ValueError:

        lsb_bits = 1


    # --------------------------------------------------------
    # VALIDASI KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "jpeg_test.html",

            success=False,

            message_intact=False,

            original_message=
                original_message,

            extracted_message=
                None,

            jpeg_filename=
                jpeg_filename,

            selected_m=
                lsb_bits,

            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    try:

        # ====================================================
        # BACA JPEG
        # ====================================================

        if jpeg_data_base64:

            jpeg_bytes = base64.b64decode(
                jpeg_data_base64
            )


            jpeg_image = Image.open(
                BytesIO(jpeg_bytes)
            ).convert(
                "RGB"
            )


        else:

            # Fallback untuk penggunaan lokal.

            if not jpeg_filename:

                raise ValueError(
                    "File JPEG tidak ditemukan."
                )


            jpeg_path = os.path.join(
                app.config["OUTPUT_FOLDER"],
                jpeg_filename
            )


            if not os.path.exists(
                jpeg_path
            ):

                raise ValueError(
                    "File JPEG tidak ditemukan."
                )


            jpeg_image = Image.open(
                jpeg_path
            ).convert(
                "RGB"
            )


        # ====================================================
        # DECODE M-BIT
        # ====================================================

        encrypted_message = decode_mbit_data(
            jpeg_image,
            stego_key,
            lsb_bits
        )


        # ====================================================
        # DEKRIPSI
        # ====================================================

        extracted_message = decrypt_message(
            encrypted_message,
            stego_key
        )


        # ====================================================
        # BANDINKAN PESAN
        # ====================================================

        if (
            extracted_message
            == original_message
        ):

            return render_template(
                "jpeg_test.html",

                success=True,

                message_intact=True,

                original_message=
                    original_message,

                extracted_message=
                    extracted_message,

                jpeg_filename=
                    jpeg_filename,

                selected_m=
                    lsb_bits,

                error=None
            )


        else:

            return render_template(
                "jpeg_test.html",

                success=True,

                message_intact=False,

                original_message=
                    original_message,

                extracted_message=
                    extracted_message,

                jpeg_filename=
                    jpeg_filename,

                selected_m=
                    lsb_bits,

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

            original_message=
                original_message,

            extracted_message=
                None,

            jpeg_filename=
                jpeg_filename,

            selected_m=
                lsb_bits,

            error=(
                f"Decode JPEG gagal: {str(e)}"
            )
        )


# ============================================================
# NORMAL DECODE
# ============================================================

@app.route(
    "/decode",
    methods=[
        "GET",
        "POST"
    ]
)
def decode():

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "decode.html"
        )


    # --------------------------------------------------------
    # INPUT
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
    # VALIDASI KEY
    # --------------------------------------------------------

    if not stego_key:

        return render_template(
            "decode.html",

            error=(
                "Stego-key tidak boleh kosong."
            )
        )


    try:

        # ====================================================
        # SIMPAN STEGO IMAGE
        # ====================================================

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


        # ====================================================
        # BUKA IMAGE
        # ====================================================

        stego_image = Image.open(
            input_path
        ).convert(
            "RGB"
        )


        # ====================================================
        # AUTO-DETECT 1-4 BIT
        # ====================================================

        extracted_message = None
        detected_bits = None


        for m in (
            1,
            2,
            3,
            4
        ):

            try:

                encrypted_message = (
                    decode_mbit_data(
                        stego_image,
                        stego_key,
                        m
                    )
                )


                candidate_message = (
                    decrypt_message(
                        encrypted_message,
                        stego_key
                    )
                )


                extracted_message = (
                    candidate_message
                )


                detected_bits = m


                break


            except Exception:

                continue


        # ====================================================
        # JIKA SEMUA GAGAL
        # ====================================================

        if extracted_message is None:

            raise ValueError(
                "Gagal melakukan decode. "
                "Stego-key mungkin salah atau "
                "format/bit LSB tidak sesuai."
            )


        # ====================================================
        # HASIL
        # ====================================================

        return render_template(

            "decode.html",

            success=True,

            message=
                extracted_message,

            filename=
                filename,

            detected_bits=
                detected_bits

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
# OUTPUT IMAGE
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
# UPLOAD IMAGE
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