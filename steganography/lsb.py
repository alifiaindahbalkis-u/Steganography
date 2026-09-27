from PIL import Image

from steganography.prng import generate_positions


# ============================================================
# KONSTANTA HEADER
# ============================================================

MAGIC = b"STG1"

# MAGIC = 4 byte
# VERSION = 1 byte
# LENGTH = 4 byte
HEADER_SIZE = 9


# ============================================================
# KONVERSI DATA KE BIT
# ============================================================

def bytes_to_bits(data: bytes) -> list[int]:
    """
    Mengubah bytes menjadi list bit 0 dan 1.
    """

    bits = []

    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)

    return bits


def bits_to_bytes(bits: list[int]) -> bytes:
    """
    Mengubah list bit menjadi bytes.
    """

    if len(bits) % 8 != 0:
        raise ValueError("Jumlah bit harus kelipatan 8.")

    result = bytearray()

    for i in range(0, len(bits), 8):
        byte = 0

        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit

        result.append(byte)

    return bytes(result)


# ============================================================
# HEADER
# ============================================================

def create_header(payload_length: int) -> bytes:
    """
    Membuat header:

    MAGIC   : 4 byte
    VERSION : 1 byte
    LENGTH  : 4 byte
    """

    if payload_length < 0:
        raise ValueError("Panjang payload tidak valid.")

    return (
        MAGIC
        + bytes([1])
        + payload_length.to_bytes(4, byteorder="big")
    )


def parse_header(header: bytes) -> int:
    """
    Membaca header dan mengembalikan panjang payload.
    """

    if len(header) != HEADER_SIZE:
        raise ValueError("Header tidak lengkap.")

    if header[:4] != MAGIC:
        raise ValueError("Format steganografi tidak valid.")

    version = header[4]

    if version != 1:
        raise ValueError("Versi steganografi tidak didukung.")

    payload_length = int.from_bytes(
        header[5:9],
        byteorder="big"
    )

    return payload_length


# ============================================================
# KAPASITAS
# ============================================================

def get_capacity(image: Image.Image) -> int:
    """
    Menghitung kapasitas data yang dapat disimpan
    dalam byte.

    Menggunakan 1 LSB dari setiap channel RGB.
    """

    rgb_image = image.convert("RGB")

    width, height = rgb_image.size

    total_channels = width * height * 3

    total_bytes = total_channels // 8

    # Kurangi ruang untuk header
    available_bytes = total_bytes - HEADER_SIZE

    return max(0, available_bytes)


# ============================================================
# ENCODE / EMBED
# ============================================================

def encode_data(
    image: Image.Image,
    payload: bytes,
    stego_key: str
) -> Image.Image:
    """
    Menyisipkan payload ke dalam gambar menggunakan LSB.
    """

    image = image.convert("RGB")

    width, height = image.size

    # Data yang sebenarnya disisipkan:
    # header + payload
    header = create_header(len(payload))

    data = header + payload

    bits = bytes_to_bits(data)

    total_channels = width * height * 3

    if len(bits) > total_channels:
        raise ValueError(
            "Payload terlalu besar untuk gambar."
        )

    # Tentukan posisi channel secara pseudo-random
    positions = generate_positions(
        total_channels,
        len(bits),
        stego_key
    )

    # Salin data pixel
    pixels = list(image.getdata())

    # Flatten RGB
    channels = []

    for pixel in pixels:
        channels.extend(pixel)

    # Ubah LSB channel
    for position, bit in zip(positions, bits):
        channels[position] = (
            channels[position] & 0xFE
        ) | bit

    # Kembalikan menjadi RGB
    new_pixels = []

    for i in range(0, len(channels), 3):
        new_pixels.append(
            (
                channels[i],
                channels[i + 1],
                channels[i + 2]
            )
        )

    stego_image = Image.new(
        "RGB",
        (width, height)
    )

    stego_image.putdata(new_pixels)

    return stego_image


# ============================================================
# DECODE / EXTRACT
# ============================================================

def decode_data(
    image: Image.Image,
    stego_key: str
) -> bytes:
    """
    Mengambil payload dari gambar stego.
    """

    image = image.convert("RGB")

    width, height = image.size

    total_channels = width * height * 3

    # --------------------------------------------------------
    # Ambil header terlebih dahulu
    # --------------------------------------------------------

    header_bits_count = HEADER_SIZE * 8

    header_positions = generate_positions(
        total_channels,
        header_bits_count,
        stego_key
    )

    pixels = list(image.getdata())

    channels = []

    for pixel in pixels:
        channels.extend(pixel)

    header_bits = []

    for position in header_positions:
        header_bits.append(
            channels[position] & 1
        )

    header = bits_to_bytes(header_bits)

    payload_length = parse_header(header)

    # --------------------------------------------------------
    # Ambil header + payload
    # --------------------------------------------------------

    total_bits_needed = (
        HEADER_SIZE + payload_length
    ) * 8

    if total_bits_needed > total_channels:
        raise ValueError(
            "Ukuran payload tidak valid."
        )

    positions = generate_positions(
        total_channels,
        total_bits_needed,
        stego_key
    )

    data_bits = []

    for position in positions:
        data_bits.append(
            channels[position] & 1
        )

    data = bits_to_bytes(data_bits)

    # Buang header
    payload = data[HEADER_SIZE:]

    return payload
