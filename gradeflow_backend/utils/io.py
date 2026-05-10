from gradeflow_engine.io.sources import BytesSource, StringSource
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


def source_from_data(data: str | bytes | bytearray) -> StringSource | BytesSource:
    """
    Build an engine source object from a str or bytes-like payload.
    - bytes/bytearray -> application/octet-stream with extension 'bin'
    - str             -> text/plain with extension 'txt'
    """
    if isinstance(data, (bytes, bytearray)):
        return BytesSource(
            data=bytes(data),
            media_type="application/octet-stream",
            extension="bin",
        )
    return StringSource(
        data=str(data),
        media_type="text/plain",
        extension="txt",
    )
