from gradeflow_backend.utils.io import blob_from_str, source_from_data


def test_blob_from_str_encodes_to_bytes() -> None:
    blob = blob_from_str("hello: world", media_type="application/yaml", ext="yaml")
    assert isinstance(blob.data, bytes)
    assert blob.data == b"hello: world"


def test_blob_from_str_sets_media_type_and_extension() -> None:
    blob = blob_from_str("data", media_type="application/json", ext="json")
    assert blob.media_type == "application/json"
    assert blob.extension == "json"


def test_source_from_data_bytes_returns_blob() -> None:
    blob = source_from_data(b"\x00\x01\x02").read()
    assert blob.media_type == "application/octet-stream"
    assert blob.extension == "bin"


def test_source_from_data_str_returns_blob() -> None:
    blob = source_from_data("hello").read()
    assert blob.media_type == "text/plain"
    assert blob.extension == "txt"


def test_source_from_data_bytearray_treated_as_bytes() -> None:
    blob = source_from_data(bytearray(b"abc")).read()
    assert blob.data == b"abc"
