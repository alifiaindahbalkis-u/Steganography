import hashlib
import random
from array import array


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


class PositionSequence:

    def __init__(self, total_elements: int, stego_key: str):
        self.total_elements = total_elements
        self.stego_key = stego_key
        self._positions = None

    def get_positions(self, required_elements: int):

        if required_elements > self.total_elements:
            raise ValueError(
                "Data yang akan disisipkan melebihi kapasitas gambar."
            )

        if self._positions is None:
            typecode = "I" if self.total_elements <= 0xFFFFFFFF else "Q"
            positions = array(typecode, range(self.total_elements))
            create_rng(self.stego_key).shuffle(positions)
            self._positions = positions

        return self._positions[:required_elements]