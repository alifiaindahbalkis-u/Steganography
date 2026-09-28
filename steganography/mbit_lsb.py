from PIL import Image

from steganography.prng import generate_positions

from steganography.lsb import (
    bytes_to_bits,
    bits_to_bytes,
    create_header,
    parse_header,
    HEADER_SIZE
)


SUPPORTED_M = (1, 2, 3, 4)


def validate_m(m: int):
    """
    Memastikan nilai m hanya 1, 2, 3, atau 4.
    """

    if m not in SUPPORTED_M:
        raise ValueError(
            "Nilai m-bit harus 1, 2, 3, atau 4."
        )


def prepare_image(
    image: Image.Image
) -> Image.Image:
    """
    Mempertahankan RGB/RGBA.
    """

    if image.mode in (
        "RGB",
        "RGBA"
    ):
        return image

    if (
        image.mode == "P"
        and "transparency" in image.info
    ):
        return image.convert("RGBA")

    if image.mode == "LA":
        return image.convert("RGBA")

    return image.convert("RGB")


def get_mbit_capacity(
    image: Image.Image,
    m: int
) -> int:
    """
    Menghitung kapasitas data berdasarkan m-bit LSB.

    Hanya channel RGB yang digunakan.
    Alpha tidak digunakan untuk penyisipan.
    """

    validate_m(m)

    image = prepare_image(image)

    width, height = image.size

    # 3 channel RGB per pixel
    total_channels = (
        width
        * height
        * 3
    )

    # Setiap channel membawa m bit
    total_bits = (
        total_channels
        * m
    )

    total_bytes = (
        total_bits
        // 8
    )

    # Sisihkan header
    available_bytes = (
        total_bytes
        - HEADER_SIZE
    )

    return max(
        0,
        available_bytes
    )


def get_rgb_channels(
    image: Image.Image
):
    """
    Mengambil seluruh channel RGB
    dari gambar.
    """

    pixels = list(
        image.getdata()
    )

    channels = []

    for pixel in pixels:

        r, g, b = pixel[:3]

        channels.extend(
            [
                r,
                g,
                b
            ]
        )

    return pixels, channels


def rebuild_image(
    image: Image.Image,
    pixels,
    channels
) -> Image.Image:
    """
    Membuat kembali gambar setelah
    perubahan channel RGB.

    Alpha dipertahankan.
    """

    width, height = image.size

    new_pixels = []


    if image.mode == "RGBA":

        for i, pixel in enumerate(
            pixels
        ):

            alpha = pixel[3]

            r = channels[
                i * 3
            ]

            g = channels[
                i * 3 + 1
            ]

            b = channels[
                i * 3 + 2
            ]

            new_pixels.append(
                (
                    r,
                    g,
                    b,
                    alpha
                )
            )

        result = Image.new(
            "RGBA",
            (width, height)
        )


    else:

        for i in range(
            0,
            len(channels),
            3
        ):

            new_pixels.append(
                (
                    channels[i],
                    channels[i + 1],
                    channels[i + 2]
                )
            )

        result = Image.new(
            "RGB",
            (width, height)
        )


    result.putdata(
        new_pixels
    )

    return result


def extract_bits_from_positions(
    channels,
    positions,
    m: int
):
    """
    Mengambil m bit dari setiap channel
    yang dipilih oleh PRNG.
    """

    mask = (
        (1 << m) - 1
    )

    bits = []

    for position in positions:

        value = (
            channels[position]
            & mask
        )

        for shift in range(
            m - 1,
            -1,
            -1
        ):

            bits.append(
                (value >> shift) & 1
            )

    return bits


def encode_mbit_data(
    image: Image.Image,
    payload: bytes,
    stego_key: str,
    m: int
) -> Image.Image:
    """
    Menyisipkan payload menggunakan
    m-bit LSB pada channel RGB.
    """

    validate_m(m)

    image = prepare_image(
        image
    )

    width, height = image.size

    # --------------------------------------------------------
    # HEADER + PAYLOAD
    # --------------------------------------------------------

    header = create_header(
        len(payload)
    )

    data = (
        header
        + payload
    )

    bits = bytes_to_bits(
        data
    )


    # --------------------------------------------------------
    # TOTAL CHANNEL
    # --------------------------------------------------------

    total_channels = (
        width
        * height
        * 3
    )


    # --------------------------------------------------------
    # JUMLAH CHANNEL YANG DIBUTUHKAN
    # --------------------------------------------------------

    required_channels = (
        len(bits) + m - 1
    ) // m


    if required_channels > total_channels:

        raise ValueError(
            "Payload terlalu besar "
            "untuk kapasitas gambar."
        )


    # --------------------------------------------------------
    # POSISI PRNG
    # --------------------------------------------------------

    positions = generate_positions(
        total_channels,
        required_channels,
        stego_key
    )


    # --------------------------------------------------------
    # CHANNEL RGB
    # --------------------------------------------------------

    pixels, channels = get_rgb_channels(
        image
    )


    # --------------------------------------------------------
    # MASK m-BIT
    # --------------------------------------------------------

    mask = (
        (1 << m) - 1
    )


    # --------------------------------------------------------
    # SISIPKAN DATA
    # --------------------------------------------------------

    for index, position in enumerate(
        positions
    ):

        start = (
            index * m
        )

        chunk = bits[
            start:start + m
        ]


        value = 0


        for bit in chunk:

            value = (
                value << 1
            ) | bit


        # Padding jika bit terakhir
        # tidak memenuhi m bit.
        if len(chunk) < m:

            value <<= (
                m - len(chunk)
            )


        channels[position] = (
            channels[position]
            & ~mask
        ) | value


    # --------------------------------------------------------
    # BANGUN GAMBAR
    # --------------------------------------------------------

    return rebuild_image(
        image,
        pixels,
        channels
    )


def decode_mbit_data(
    image: Image.Image,
    stego_key: str,
    m: int
) -> bytes:
    """
    Mengekstrak payload menggunakan
    m-bit LSB.
    """

    validate_m(m)

    image = prepare_image(
        image
    )

    # Decode RGB saja
    image = image.convert(
        "RGB"
    )

    width, height = image.size

    total_channels = (
        width
        * height
        * 3
    )


    # --------------------------------------------------------
    # AMBIL CHANNEL
    # --------------------------------------------------------

    pixels = list(
        image.getdata()
    )

    channels = []

    for pixel in pixels:

        r, g, b = pixel

        channels.extend(
            [
                r,
                g,
                b
            ]
        )


    # ========================================================
    # BACA HEADER
    # ========================================================

    header_bits_count = (
        HEADER_SIZE * 8
    )


    # Berapa channel yang dibutuhkan
    # untuk membaca header.
    header_channels = (
        header_bits_count + m - 1
    ) // m


    header_positions = generate_positions(
        total_channels,
        header_channels,
        stego_key
    )


    header_bits = (
        extract_bits_from_positions(
            channels,
            header_positions,
            m
        )
    )


    # Buang padding.
    header_bits = header_bits[
        :header_bits_count
    ]


    header = bits_to_bytes(
        header_bits
    )


    # --------------------------------------------------------
    # BACA PANJANG PAYLOAD
    # --------------------------------------------------------

    payload_length = parse_header(
        header
    )


    # ========================================================
    # TOTAL DATA
    # ========================================================

    total_bits_needed = (
        HEADER_SIZE
        + payload_length
    ) * 8


    required_channels = (
        total_bits_needed
        + m
        - 1
    ) // m


    if required_channels > total_channels:

        raise ValueError(
            "Ukuran payload tidak valid."
        )


    # ========================================================
    # EKSTRAK DATA
    # ========================================================

    positions = generate_positions(
        total_channels,
        required_channels,
        stego_key
    )


    data_bits = (
        extract_bits_from_positions(
            channels,
            positions,
            m
        )
    )


    data_bits = data_bits[
        :total_bits_needed
    ]


    data = bits_to_bytes(
        data_bits
    )


    # Hapus header
    payload = data[
        HEADER_SIZE:
    ]


    return payload