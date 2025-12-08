from gradeflow_engine.io.sources import BytesSource, DataSource, StringSource
from gradeflow_engine.serializations.base import DataBlob


def blob_from_str(data: str, media_type: str, ext: str) -> DataBlob:
    """
    Build an engine DataBlob from a string payload.

    - data: textual content
    - media_type: IANA media type (e.g., application/yaml, application/json, text/csv)
    - ext: file extension without dot (e.g., yaml, json, csv)

    Returns a DataBlob suitable for engine serializer loads.
    """
    return DataBlob(data=data.encode("utf-8"), media_type=media_type, extension=ext)


def source_from_data(data: str | bytes) -> DataSource:
    """
    Build a DataSource from a str or bytes payload.
    - bytes -> BytesSource with default media_type 'application/octet-stream' and extension 'bin'
    - str   -> StringSource with default media_type 'text/plain' and extension 'txt'
    """
    if isinstance(data, (bytes, bytearray)):
        return BytesSource(bytes(data), media_type="application/octet-stream", extension="bin")
    return StringSource(str(data), media_type="text/plain", extension="txt")
