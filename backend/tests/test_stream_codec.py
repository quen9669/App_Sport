"""Tests for the compact stream storage format."""

import json

from app.services.stream_codec import StreamSet, decode_streams, encode_streams, point_count


def test_round_trip_keeps_all_series() -> None:
    streams: StreamSet = {
        "time": list(range(3600)),
        "heartrate": [140 + i % 15 for i in range(3600)],
        "latlng": [[49.61 + i * 1e-5, 6.13] for i in range(3600)],
    }

    blob = encode_streams(streams)

    assert decode_streams(blob) == streams
    # Compression must actually help on repetitive series.
    assert len(blob) < len(json.dumps(streams)) / 3


def test_point_count_is_longest_series() -> None:
    assert point_count({"time": [0, 1, 2], "heartrate": [100]}) == 3
    assert point_count({}) == 0
