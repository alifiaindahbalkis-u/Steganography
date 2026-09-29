import os


# Batas ukuran file .txt pesan.
# Dijaga kecil karena pesan juga dikirim ulang lewat hidden field
# pada halaman hasil (uji JPEG), dan Flask membatasi ukuran field
# form non-file (default 500 KB).
MAX_MESSAGE_FILE_BYTES = 100 * 1024

SOURCE_MANUAL = "manual"
SOURCE_FILE = "file"


def read_message_input(source, manual_text, uploaded_file):
    """
    Mengambil pesan rahasia dari salah satu sumber:

    - "manual" : teks yang diketik di textarea
    - "file"   : isi file .txt (UTF-8) yang diupload

    Mengembalikan string pesan, atau melempar ValueError
    dengan pesan yang siap ditampilkan ke pengguna.
    """

    source = (source or SOURCE_MANUAL).strip().lower()

    if source == SOURCE_MANUAL:
        return manual_text or ""

    if source != SOURCE_FILE:
        raise ValueError("Sumber pesan tidak valid.")

    if uploaded_file is None or not uploaded_file.filename:
        raise ValueError("Silakan pilih file .txt terlebih dahulu.")

    filename = os.path.basename(uploaded_file.filename)

    if not filename.lower().endswith(".txt"):
        raise ValueError("File pesan harus berformat .txt.")

    # Baca maksimal batas + 1 byte agar file besar tidak dimuat penuh.
    raw = uploaded_file.stream.read(MAX_MESSAGE_FILE_BYTES + 1)

    if len(raw) > MAX_MESSAGE_FILE_BYTES:
        raise ValueError(
            "Ukuran file .txt maksimal "
            f"{MAX_MESSAGE_FILE_BYTES // 1024} KB."
        )

    try:
        # utf-8-sig otomatis membuang BOM dari file Notepad.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(
            "File .txt harus berencoding UTF-8."
        ) from None

    if not text.strip():
        raise ValueError("File .txt tidak boleh kosong.")

    return text
