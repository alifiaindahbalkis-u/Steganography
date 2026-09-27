from steganography.encryption import (
    encrypt_message,
    decrypt_message
)


def test_encrypt_decrypt():
    message = "Pesan rahasia steganografi"
    password = "kunci-rahasia-123"

    encrypted = encrypt_message(
        message,
        password
    )

    decrypted = decrypt_message(
        encrypted,
        password
    )

    assert decrypted == message


def test_wrong_password():
    message = "Pesan rahasia"
    password = "password-benar"
    wrong_password = "password-salah"

    encrypted = encrypt_message(
        message,
        password
    )

    try:
        decrypt_message(
            encrypted,
            wrong_password
        )

        assert False, "Seharusnya dekripsi gagal."

    except ValueError:
        assert True