import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_key(password: str, salt: bytes) -> bytes:
    """
    Mengubah password/stego-key menjadi AES-256 key
    menggunakan PBKDF2-HMAC-SHA256.
    """

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )

    return kdf.derive(password.encode("utf-8"))


def encrypt_message(message: str, password: str) -> bytes:
    """
    Mengenkripsi pesan menggunakan AES-256-GCM.

    Format hasil:
    salt + nonce + ciphertext
    """

    # Salt dibuat secara aman
    salt = os.urandom(16)

    # Turunkan password menjadi AES-256 key
    key = derive_key(password, salt)

    # Nonce AES-GCM
    nonce = os.urandom(12)

    # AES-GCM
    aes = AESGCM(key)

    ciphertext = aes.encrypt(
        nonce,
        message.encode("utf-8"),
        None
    )

    # Gabungkan agar mudah disimpan ke dalam stego image
    return salt + nonce + ciphertext


def decrypt_message(encrypted_data: bytes, password: str) -> str:
    """
    Mendekripsi data hasil encrypt_message().
    """

    # Minimal:
    # 16 byte salt + 12 byte nonce + ciphertext
    if len(encrypted_data) < 29:
        raise ValueError("Data terenkripsi tidak valid.")

    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    ciphertext = encrypted_data[28:]

    # Buat kembali AES key
    key = derive_key(password, salt)

    aes = AESGCM(key)

    try:
        plaintext = aes.decrypt(
            nonce,
            ciphertext,
            None
        )
    except Exception:
        raise ValueError(
            "Gagal mendekripsi. Password/key mungkin salah."
        )

    return plaintext.decode("utf-8")