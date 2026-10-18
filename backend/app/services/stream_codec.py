"""Compact storage format for activity time series (streams).

A stream set is a dict such as ``{"time": [0, 1, 2], "heartrate": [120, 121, 123],
"latlng": [[49.61, 6.13], ...]}``. We serialise it to JSON and compress it with
zlib: GPS and heart-rate series are very repetitive, so they typically shrink
to a fraction of their size.
"""

import json
import zlib
from typing import Any

StreamSet = dict[str, list[Any]]

# Bump this if the format ever changes, so old rows can still be decoded.
_FORMAT_VERSION = 1


def encode_streams(streams: StreamSet) -> bytes:
    """Serialise and compress a stream set."""
    document = {"v": _FORMAT_VERSION, "streams": streams}
    # separators=(",", ":") removes spaces: smaller before compression even starts.
    raw = json.dumps(document, separators=(",", ":")).encode()
    return zlib.compress(raw, level=6)


def decode_streams(blob: bytes) -> StreamSet:
    """Inverse of :func:`encode_streams`."""
    document = json.loads(zlib.decompress(blob))
    if document.get("v") != _FORMAT_VERSION:
        raise ValueError(f"Unsupported stream format version: {document.get('v')!r}")
    streams: StreamSet = document["streams"]
    return streams


def point_count(streams: StreamSet) -> int:
    """Number of samples (length of the longest series)."""
    return max((len(series) for series in streams.values()), default=0)
