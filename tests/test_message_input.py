import io

import pytest
from werkzeug.datastructures import FileStorage

from steganography.message_input import (
    MAX_MESSAGE_FILE_BYTES,
    read_message_input,
)


def make_file(content: bytes, name: str = "pesan.txt"):
    return FileStorage(stream=io.BytesIO(content), filename=name)


def test_manual_source_returns_typed_text():
    assert read_message_input("manual", "halo", None) == "halo"


def test_default_source_is_manual():
    assert read_message_input(None, "halo", None) == "halo"


def test_file_source_reads_utf8_text():
    f = make_file("Pesan rahasia é 你好".encode("utf-8"))
    assert read_message_input("file", "", f) == "Pesan rahasia é 你好"


def test_file_source_strips_bom():
    f = make_file(b"\xef\xbb\xbfhalo")
    assert read_message_input("file", "", f) == "halo"


def test_file_source_ignores_manual_text():
    f = make_file(b"dari file")
    assert read_message_input("file", "dari textarea", f) == "dari file"


def test_file_source_without_file_fails():
    with pytest.raises(ValueError):
        read_message_input("file", "", None)


def test_file_source_wrong_extension_fails():
    with pytest.raises(ValueError):
        read_message_input("file", "", make_file(b"halo", "pesan.docx"))


def test_file_source_empty_fails():
    with pytest.raises(ValueError):
        read_message_input("file", "", make_file(b"  \n "))


def test_file_source_too_large_fails():
    big = b"a" * (MAX_MESSAGE_FILE_BYTES + 1)
    with pytest.raises(ValueError):
        read_message_input("file", "", make_file(big))


def test_file_source_invalid_utf8_fails():
    with pytest.raises(ValueError):
        read_message_input("file", "", make_file(b"\xff\xfe\x00\x80"))


def test_unknown_source_fails():
    with pytest.raises(ValueError):
        read_message_input("lainnya", "halo", None)
