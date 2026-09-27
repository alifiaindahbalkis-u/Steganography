import hashlib
import random


def create_rng(stego_key: str) -> random.Random:
    """
    Membuat PRNG deterministik berdasarkan stego-key.

    Key yang sama -> urutan posisi yang sama.
    Key berbeda -> urutan posisi berbeda.
    """

    # Ubah stego-key menjadi nilai hash
    key_hash = hashlib.sha256(
        stego_key.encode("utf-8")
    ).digest()

    # Ubah hasil hash menjadi integer
    seed = int.from_bytes(
        key_hash,
        byteorder="big"
    )

    return random.Random(seed)


def generate_positions(
    total_elements: int,
    required_elements: int,
    stego_key: str
) -> list[int]:
    """
    Menghasilkan posisi pixel/channel yang akan digunakan
    untuk menyimpan data.
    """

    if required_elements > total_elements:
        raise ValueError(
            "Data yang akan disisipkan melebihi kapasitas gambar."
        )

    rng = create_rng(stego_key)

    positions = list(range(total_elements))

    rng.shuffle(positions)

    return positions[:required_elements]