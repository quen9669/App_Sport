"""Google "encoded polyline" format, used by Strava and by map libraries.

A route is a list of (latitude, longitude) points. The encoding stores each
point as the *difference* from the previous one, rounded to 5 decimals, and
writes every number as a few printable characters. A route of thousands of
points becomes a short string. Spec:
https://developers.google.com/maps/documentation/utilities/polylinealgorithm
"""

from collections.abc import Iterable

Point = tuple[float, float]


def _encode_number(value: int) -> str:
    # Left-shift, and invert if negative, so the sign ends up in the lowest bit.
    value = ~(value << 1) if value < 0 else value << 1
    chunks = []
    while value >= 0x20:
        # 5 bits per character; 0x20 marks "another chunk follows".
        chunks.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    chunks.append(chr(value + 63))
    return "".join(chunks)


def encode(points: Iterable[Point]) -> str:
    result = []
    previous_lat = previous_lng = 0
    for lat, lng in points:
        lat_e5, lng_e5 = round(lat * 1e5), round(lng * 1e5)
        result.append(_encode_number(lat_e5 - previous_lat))
        result.append(_encode_number(lng_e5 - previous_lng))
        previous_lat, previous_lng = lat_e5, lng_e5
    return "".join(result)


def decode(encoded: str) -> list[Point]:
    points: list[Point] = []
    index = lat = lng = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):  # one latitude delta, then one longitude delta
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        points.append((lat / 1e5, lng / 1e5))
    return points
