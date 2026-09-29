import os
import base64
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from secrets import compare_digest, token_urlsafe
from uuid import uuid4
from datetime import timedelta

from io import BytesIO

from dotenv import load_dotenv

from flask import (
    abort,
    Flask,
    render_template,
    redirect,
    request,
    session,
    send_file,
    url_for
)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

from PIL import Image

from steganography.supabase_store import (
    insert_row,
    insert_rows,
    list_recent_runs,
    upload_history_image,
    download_history_image,
    delete_history_image
)
from steganography.batch_encode import encode_batch_item
from steganography.message_input import read_message_input

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

load_dotenv()

APP_ENV = os.environ.get(
    "APP_ENV",
    "development"
).lower()

IS_PRODUCTION = (
    APP_ENV == "production"
    or os.environ.get("VERCEL") == "1"
)

# Rate limit storage.
# Jika RATELIMIT_STORAGE_URI belum tersedia,
# gunakan memory storage.
RATELIMIT_STORAGE_URI = os.environ.get(
    "RATELIMIT_STORAGE_URI",
    "memory://"
)

flask_secret_key = os.environ.get(
    "FLASK_SECRET_KEY"
)

if not flask_secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY must be configured."
    )
    
app = Flask(__name__)
app.config.update(
    SECRET_KEY=flask_secret_key,
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=RATELIMIT_STORAGE_URI,
    strategy="fixed-window",
)


@app.after_request
def add_security_headers(response):

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


def finite_metric(value):

    if value is None or not math.isfinite(value):
        return None

    return value


def save_run(
    run_data,
    mode_results=None,
    source_image=None,
    result_image=None
):

    run_id = str(uuid4())
    uploaded_paths = []
    row_inserted = False

    try:

        values = {
            **run_data,
            "id": run_id,
            "source_image_path": None,
            "result_image_path": None,
        }

        upload_tasks = []

        for kind, image, column in (
            ("source", source_image, "source_image_path"),
            ("result", result_image, "result_image_path"),
        ):

            if image is None:
                continue

            object_path = f"{run_id}/{kind}.png"
            uploaded_paths.append(object_path)
            values[column] = object_path
            upload_tasks.append((
                object_path,
                image_to_png_bytes(image)
            ))

        if upload_tasks:

            with ThreadPoolExecutor(
                max_workers=len(upload_tasks)
            ) as executor:

                futures = [
                    executor.submit(
                        upload_history_image,
                        object_path,
                        image_bytes
                    )
                    for object_path, image_bytes in upload_tasks
                ]

                for future in as_completed(futures):
                    future.result()

        run = insert_row(
            "steganography_runs",
            values
        )
        row_inserted = True

        if mode_results:

            insert_rows(
                "bit_mode_results",
                [
                    {
                        **result,
                        "run_id": run["id"]
                    }
                    for result in mode_results
                ]
            )

        return True

    except Exception as error:

        if not row_inserted:

            for object_path in uploaded_paths:

                try:
                    delete_history_image(object_path)
                except Exception:
                    pass

        app.logger.warning(
            "Supabase history save failed (%s).",
            type(error).__name__
        )

        return False


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
# pia
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


def image_to_png_bytes(image):

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    return buffer.getvalue()


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
            "encode_batch.html"
        )


    # --------------------------------------------------------
    # AMBIL INPUT
    # --------------------------------------------------------

    image_file = request.files.get(
        "image"
    )


    # Pesan bisa diketik manual atau diambil dari file .txt
    try:

        message = read_message_input(
            request.form.get(
                "message_source",
                "manual"
            ),
            request.form.get(
                "message",
                ""
            ),
            request.files.get(
                "message_file"
            )
        )

    except ValueError as e:

        return render_template(
            "encode.html",
            error=str(e)
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


        mode_statuses = []

        for result in comparison_results:

            if result["encrypted_size"] > result["capacity"]:
                mode_status = "insufficient_capacity"

            elif result["status"] == "PASS":
                mode_status = "pass"

            else:
                mode_status = "fail"

            mode_statuses.append({
                "bits_per_channel": result["m"],
                "capacity_bytes": result["capacity"],
                "plaintext_capacity_bytes": result["plaintext_capacity"],
                "encrypted_payload_bytes": result["encrypted_size"],
                "mse": finite_metric(result["mse"]),
                "psnr_db": finite_metric(result["psnr"]),
                "status": mode_status,
            })


        database_saved = save_run(
            {
                "operation": "encode",
                "status": "success",
                "image_name": filename,
                "image_width": original_image.width,
                "image_height": original_image.height,
                "selected_bits": selected_m,
                "message_length_bytes": message_length,
                "encrypted_payload_bytes": encrypted_length,
                "capacity_bytes": selected_capacity,
                "mse": finite_metric(mse),
                "psnr_db": finite_metric(psnr),
                "extraction_success": True,
            },
            mode_statuses,
            source_image=original_image,
            result_image=selected_stego_image
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

            database_saved=
                database_saved,


            error=None

        )


    except Exception as e:

        app.logger.exception(
            "Single-image encoding failed."
        )

        return render_template(
            "encode.html",

            error="Encoding gagal. Periksa gambar dan input lalu coba lagi."
        )


@app.route(
    "/encode/batch",
    methods=["POST"]
)
def encode_batch():

    try:
        item_count = int(
            request.form.get("item_count", "0")
        )
    except ValueError:
        item_count = 0

    if item_count < 1 or item_count > 5:
        return render_template(
            "encode_batch.html",
            results=[],
            error="Pilih minimal 1 dan maksimal 5 gambar.",
        ), 400

    results = []

    for index in range(item_count):
        image_file = request.files.get(
            f"image_{index}"
        )
        message = ""
        stego_key = request.form.get(
            f"stego_key_{index}",
            ""
        )
        compare_all_modes = (
            request.form.get(
                f"compare_all_modes_{index}"
            ) == "on"
        )
        image_name = secure_filename(
            os.path.basename(
                image_file.filename if image_file else ""
            )
        )
        selected_bits = None

        try:
            selected_bits = validate_m_bit(
                request.form.get(
                    f"lsb_bits_{index}",
                    "1"
                )
            )

            if not image_file or not image_file.filename:
                raise ValueError("Pilih gambar untuk item ini.")

            message = read_message_input(
                request.form.get(
                    f"message_source_{index}",
                    "manual"
                ),
                request.form.get(
                    f"message_{index}",
                    ""
                ),
                request.files.get(
                    f"message_file_{index}"
                )
            )

            result = encode_batch_item(
                image_file,
                message,
                stego_key,
                selected_bits,
                compare_all_modes=compare_all_modes,
            )
            image_name = result["filename"]
            selected_comparison = next(
                mode for mode in result["comparison_results"]
                if mode["m"] == selected_bits
            )

            run_data = {
                "operation": "encode",
                "status": "success" if result["success"] else "failed",
                "image_name": image_name,
                "image_width": result["original_image"].width,
                "image_height": result["original_image"].height,
                "selected_bits": selected_bits,
                "message_length_bytes": result["message_length"],
                "encrypted_payload_bytes": result["encrypted_length"],
                "capacity_bytes": result["capacity"],
                "mse": finite_metric(selected_comparison["mse"]),
                "psnr_db": finite_metric(selected_comparison["psnr"]),
                "extraction_success": result["success"],
            }
            result["run_data"] = run_data

            if result["success"]:

                filename_stem = os.path.splitext(
                    image_name
                )[0]

                output_prefix = (
                    f"{index + 1:02d}_{filename_stem}"
                )


                # =====================================================
                # NAMA FILE HASIL
                # =====================================================

                result["output_filename"] = (
                    f"stego_{output_prefix}_{selected_bits}bit.png"
                )

                result["lsb_filename"] = (
                    f"lsb_{output_prefix}_{selected_bits}bit.png"
                )

                result["jpeg_filename"] = (
                    f"jpeg_test_{output_prefix}_{selected_bits}bit.jpg"
                )


                # =====================================================
                # DATA URI COVER / STEGO / LSB
                # =====================================================

                result["cover_data_uri"] = image_to_data_uri(
                    result["original_image"],
                    "PNG"
                )

                result["stego_data_uri"] = image_to_data_uri(
                    result["stego_image"],
                    "PNG"
                )

                result["lsb_data_uri"] = image_to_data_uri(
                    result["lsb_image"],
                    "PNG"
                )


                # =====================================================
                # PATH OUTPUT
                # =====================================================

                output_path = os.path.join(
                    app.config["OUTPUT_FOLDER"],
                    result["output_filename"]
                )

                lsb_path = os.path.join(
                    app.config["OUTPUT_FOLDER"],
                    result["lsb_filename"]
                )

                jpeg_path = os.path.join(
                    app.config["OUTPUT_FOLDER"],
                    result["jpeg_filename"]
                )


                # =====================================================
                # SIMPAN STEGO PNG
                # =====================================================

                result["stego_image"].save(
                    output_path,
                    format="PNG"
                )


                # =====================================================
                # SIMPAN ENHANCED LSB
                # =====================================================

                result["lsb_image"].save(
                    lsb_path,
                    format="PNG"
                )


                # =====================================================
                # JPEG RE-SAVE
                # =====================================================

                save_as_jpeg(
                    result["stego_image"],
                    jpeg_path,
                    quality=75
                )


                # =====================================================
                # BUKA KEMBALI FILE JPEG
                # =====================================================

                with Image.open(jpeg_path) as opened_jpeg:

                    jpeg_image = opened_jpeg.convert(
                        "RGB"
                    )


                # =====================================================
                # SIMPAN JPEG IMAGE KE RESULT
                # =====================================================

                result["jpeg_image"] = jpeg_image


                # =====================================================
                # JPEG DATA URI
                # =====================================================

                result["jpeg_data_uri"] = image_to_data_uri(
                    jpeg_image,
                    "JPEG"
                )


                # =====================================================
                # JPEG BASE64
                # DIPAKAI UNTUK HALAMAN JPEG DECODE TEST
                # =====================================================

                result["jpeg_data_base64"] = file_to_base64(
                    jpeg_path
                )


                # =====================================================
                # DATA YANG DIBAWA KE JPEG TEST
                # =====================================================

                result["original_message"] = message

                result["lsb_bits"] = selected_bits


                # =====================================================
                # TEST DECODE JPEG
                # =====================================================

                jpeg_message_intact = False

                try:

                    jpeg_payload = decode_mbit_data(
                        jpeg_image,
                        stego_key,
                        selected_bits
                    )


                    jpeg_message_intact = (
                        decrypt_message(
                            jpeg_payload,
                            stego_key
                        )
                        == message
                    )

                except Exception:

                    jpeg_message_intact = False


                result["jpeg_message_intact"] = (
                    jpeg_message_intact
                )


                # =====================================================
                # DATA DATABASE JPEG
                # =====================================================

                jpeg_run_data = {

                    "operation":
                        "jpeg_test",

                    "status":
                        (
                            "success"
                            if jpeg_message_intact
                            else "partial"
                        ),

                    "image_name":
                        result["jpeg_filename"],

                    "image_width":
                        jpeg_image.width,

                    "image_height":
                        jpeg_image.height,

                    "selected_bits":
                        selected_bits,

                    "message_length_bytes":
                        result["message_length"],

                    "encrypted_payload_bytes":
                        result["encrypted_length"],

                    "extraction_success":
                        jpeg_message_intact,

                    "jpeg_message_intact":
                        jpeg_message_intact,

                }


                # =====================================================
                # SIMPAN DATABASE
                # =====================================================

                with ThreadPoolExecutor(
                    max_workers=2
                ) as executor:

                    encode_save = executor.submit(
                        save_run,

                        result["run_data"],

                        result["mode_results"],

                        source_image=
                            result["original_image"],

                        result_image=
                            result["stego_image"],
                    )


                    jpeg_save = executor.submit(
                        save_run,

                        jpeg_run_data,

                        source_image=
                            jpeg_image,
                    )


                    result["database_saved"] = (
                        encode_save.result()
                    )

                    result["jpeg_database_saved"] = (
                        jpeg_save.result()
                    )


                results.append(result)

                continue

                try:
                    jpeg_payload = decode_mbit_data(
                        jpeg_image,
                        stego_key,
                        selected_bits,
                    )
                    jpeg_message_intact = (
                        decrypt_message(
                            jpeg_payload,
                            stego_key,
                        ) == message
                    )
                except Exception:
                    jpeg_message_intact = False

                result["jpeg_message_intact"] = jpeg_message_intact
                jpeg_run_data = {
                    "operation": "jpeg_test",
                    "status": (
                        "success"
                        if jpeg_message_intact
                        else "partial"
                    ),
                    "image_name": result["jpeg_filename"],
                    "image_width": jpeg_image.width,
                    "image_height": jpeg_image.height,
                    "selected_bits": selected_bits,
                    "message_length_bytes": result["message_length"],
                    "encrypted_payload_bytes": result["encrypted_length"],
                    "extraction_success": jpeg_message_intact,
                    "jpeg_message_intact": jpeg_message_intact,
                }

                with ThreadPoolExecutor(max_workers=2) as executor:
                    encode_save = executor.submit(
                        save_run,
                        result["run_data"],
                        result["mode_results"],
                        source_image=result["original_image"],
                        result_image=result["stego_image"],
                    )
                    jpeg_save = executor.submit(
                        save_run,
                        jpeg_run_data,
                        source_image=jpeg_image,
                    )

                    result["database_saved"] = encode_save.result()
                    result["jpeg_database_saved"] = jpeg_save.result()

                results.append(result)
                continue

            result["error"] = result.get(
                "error",
                "Mode LSB yang dipilih tidak dapat digunakan."
            )
            results.append(result)

        except ValueError as error:
            image_bytes = len(message.encode("utf-8"))
            database_saved = save_run({
                "operation": "encode",
                "status": "failed",
                "image_name": image_name or None,
                "selected_bits": selected_bits,
                "message_length_bytes": image_bytes,
                "extraction_success": False,
            })
            results.append({
                "success": False,
                "filename": image_name or "Item gambar",
                "selected_m": selected_bits,
                "error": str(error),
                "database_saved": database_saved,
            })
        except Exception as error:
            app.logger.warning(
                "Batch image processing failed (%s).",
                type(error).__name__
            )
            results.append({
                "success": False,
                "filename": image_name or "Item gambar",
                "selected_m": selected_bits,
                "error": "Gagal memproses gambar ini. Periksa format dan kapasitasnya.",
                "database_saved": False,
            })

    return render_template(
        "encode_batch_results.html",
        results=results
    )


# ============================================================
# JPEG RE-SAVE TEST
# ============================================================

@app.route(
    "/jpeg-test",
    methods=["GET", "POST"]
)
def jpeg_test():

    if request.method == "GET":

        return redirect(
            url_for("encode")
        )

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
    # TAMPILKAN FORM JPEG DECODE TEST
    # --------------------------------------------------------

    if request.form.get("action") == "show_form":

        try:
            lsb_bits_preview = validate_m_bit(
                lsb_bits_value
            )
        except ValueError:
            lsb_bits_preview = 1

        return render_template(
            "jpeg_test.html",

            success=None,

            message_intact=None,

            original_message=original_message,

            extracted_message=None,

            jpeg_filename=jpeg_filename,

            selected_m=lsb_bits_preview,

            jpeg_data_base64=jpeg_data_base64,

            database_saved=False,

            error=None,
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

        message_intact = (
            extracted_message
            == original_message
        )

        database_saved = save_run(
            {
                "operation": "jpeg_test",
                "status": "success" if message_intact else "partial",
                "image_name": jpeg_filename,
                "image_width": jpeg_image.width,
                "image_height": jpeg_image.height,
                "selected_bits": lsb_bits,
                "message_length_bytes": len(
                    original_message.encode("utf-8")
                ),
                "encrypted_payload_bytes": len(encrypted_message),
                "extraction_success": True,
                "jpeg_message_intact": message_intact,
            },
            source_image=jpeg_image
        )


        if message_intact:

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

                database_saved=
                    database_saved,

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

                database_saved=
                    database_saved,

                error=(
                    "Pesan berhasil diekstrak, "
                    "tetapi isinya berbeda "
                    "dengan pesan asli."
                )
            )


    except Exception as e:

        app.logger.exception(
            "JPEG extraction failed."
        )

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

            error="Decode JPEG gagal. Periksa gambar dan stego-key."
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
        extracted_payload_bytes = None


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

                extracted_payload_bytes = len(
                    encrypted_message
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

        database_saved = save_run(
            {
                "operation": "decode",
                "status": "success",
                "image_name": filename,
                "image_width": stego_image.width,
                "image_height": stego_image.height,
                "detected_bits": detected_bits,
                "message_length_bytes": len(
                    extracted_message.encode("utf-8")
                ),
                "encrypted_payload_bytes": extracted_payload_bytes,
                "extraction_success": True,
            },
            source_image=stego_image
        )

        decoded_image_uri = image_to_data_uri(
            stego_image,
            "PNG"
        )

        return render_template(

            "decode.html",

            success=True,

            message=
                extracted_message,

            filename=
                filename,

            detected_bits=
                detected_bits,

            image_data_uri=
                decoded_image_uri,

            database_saved=
                database_saved

        )


    except Exception as e:

        app.logger.exception(
            "Image decoding failed."
        )

        return render_template(
            "decode.html",

            error="Decode gagal. Pastikan gambar dan stego-key benar."
        )


# ============================================================
# HISTORY
# ============================================================

@app.route(
    "/history",
    methods=["GET", "POST"]
)
@limiter.limit("5 per 15 minutes", methods=["POST"])
def history():

    history_access_key = (
        os.environ.get("HISTORY_ACCESS_KEY")
        or ""
    )

    if not history_access_key:

        return render_template(
            "history.html",
            setup_required=True
        )

    if request.method == "POST":

        submitted_csrf_token = request.form.get(
            "csrf_token",
            ""
        )
        expected_csrf_token = session.pop(
            "history_csrf_token",
            ""
        )

        if (
            not expected_csrf_token
            or not compare_digest(
                submitted_csrf_token,
                expected_csrf_token
            )
        ):

            session["history_csrf_token"] = token_urlsafe(32)

            return render_template(
                "history.html",
                auth_required=True,
                csrf_token=session["history_csrf_token"],
                error="Form kedaluwarsa. Muat ulang halaman lalu coba lagi."
            ), 400

        submitted_key = request.form.get(
            "access_key",
            ""
        )

        if compare_digest(
            submitted_key,
            history_access_key
        ):

            session.clear()
            session["history_authorized"] = True
            session.permanent = True

            return redirect(
                url_for("history")
            )

        return render_template(
            "history.html",
            auth_required=True,
            csrf_token=(
                session.setdefault(
                    "history_csrf_token",
                    token_urlsafe(32)
                )
            ),
            error="Passcode riwayat tidak cocok."
        )

    if not session.get("history_authorized"):

        session["history_csrf_token"] = token_urlsafe(32)

        return render_template(
            "history.html",
            auth_required=True,
            csrf_token=session["history_csrf_token"]
        )

    session["history_csrf_token"] = token_urlsafe(32)

    try:

        runs = list_recent_runs()

    except Exception as error:

        app.logger.warning(
            "Supabase history load failed (%s).",
            type(error).__name__
        )

        return render_template(
            "history.html",
            runs=[],
            load_error=True
        )

    return render_template(
        "history.html",
        runs=runs,
        csrf_token=session["history_csrf_token"]
    )


@app.route(
    "/history/logout",
    methods=["POST"]
)
def history_logout():

    submitted_csrf_token = request.form.get(
        "csrf_token",
        ""
    )
    expected_csrf_token = session.pop(
        "history_csrf_token",
        ""
    )

    if (
        not expected_csrf_token
        or not compare_digest(
            submitted_csrf_token,
            expected_csrf_token
        )
    ):

        abort(400)

    session.clear()

    return redirect(
        url_for("history")
    )


@app.route(
    "/history/images/<uuid:run_id>/<kind>"
)
def history_image(run_id, kind):

    history_access_key = (
        os.environ.get("HISTORY_ACCESS_KEY")
        or ""
    )

    if (
        kind not in ("source", "result")
        or not history_access_key
        or not session.get("history_authorized")
    ):

        abort(404)

    object_path = f"{run_id}/{kind}.png"

    try:

        image_bytes = download_history_image(
            object_path
        )

    except Exception as error:

        app.logger.warning(
            "Supabase history image load failed (%s).",
            type(error).__name__
        )

        abort(404)

    response = send_file(
        BytesIO(image_bytes),
        mimetype="image/png"
    )
    response.headers["Cache-Control"] = "private, no-store"

    return response


# ============================================================
# RUN LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=(
            not IS_PRODUCTION
            and os.environ.get("FLASK_DEBUG", "0") == "1"
        )
    )