# SPDX-License-Identifier: GPL-3.0-or-later
"""EXIF in plain Python (no Pillow, no Qt): read the tags the info panel shows, and turn a JPEG losslessly by
rewriting only its Orientation tag (the pixels stay byte for byte as they were).

Reads the TIFF block from JPEG (APP1 "Exif"), PNG (eXIf), WebP (EXIF chunk), TIFF and camera RAW files (the file
itself), HEIF/AVIF (the "Exif" item). Anything malformed reads as "no EXIF" instead of raising.
"""

import struct
from pathlib import Path

HEAD = 512 * 1024  # EXIF sits near the start; never read whole multi-GB files

# Orientation tag values -> the 2x2 matrix taking stored pixels to how they're shown (x right, y down)
ORIENT = {
    1: (1, 0, 0, 1),
    2: (-1, 0, 0, 1),
    3: (-1, 0, 0, -1),
    4: (1, 0, 0, -1),
    5: (0, 1, 1, 0),
    6: (0, -1, 1, 0),
    7: (0, -1, -1, 0),
    8: (0, 1, -1, 0),
}
# the user's turns, as the same kind of matrix
OPS = {"cw": (0, -1, 1, 0), "ccw": (0, 1, -1, 0), "fliph": (-1, 0, 0, 1), "flipv": (1, 0, 0, -1)}

TAGS = {
    0x010F: "make",
    0x0110: "model",
    0x0112: "orientation",
    0x0131: "software",
    0x0132: "datetime",
    0x013B: "artist",
    0x8298: "copyright",
}
EXIF_TAGS = {
    0x829A: "exposure",
    0x829D: "fnumber",
    0x8827: "iso",
    0x9003: "taken",
    0x920A: "focal",
    0xA405: "focal35",
    0xA434: "lens",
    0x9209: "flash",
    0x9204: "bias",
}
GPS_TAGS = {1: "lat_ref", 2: "lat", 3: "lon_ref", 4: "lon", 5: "alt_ref", 6: "alt"}
SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def compose(orient: int, op: str) -> int:
    """The Orientation value that shows the picture as `orient` would, then turned by op (cw, ccw, fliph, flipv)."""
    a, b, c, d = OPS[op]
    e, f, g, h = ORIENT.get(orient, ORIENT[1])
    m = (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)
    return next(k for k, v in ORIENT.items() if v == m)


def combined(ops: list[str], orient: int = 1) -> int:
    for op in ops:
        orient = compose(orient, op)
    return orient


# ---------------------------------------------------------------- finding the TIFF block
def _jpeg_app1(data: bytes) -> tuple[int, int] | None:
    """(start, end) of the TIFF block inside a JPEG's Exif APP1 segment."""
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker in (0xDA, 0xD9):  # image data starts: no more headers
            return None
        size = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker == 0xE1 and data[i + 4 : i + 10] == b"Exif\0\0":
            return i + 10, i + 2 + size
        i += 2 + size
    return None


def tiff_block(data: bytes) -> bytes:
    """The raw TIFF (EXIF) block of an image file's first bytes, b"" when there's none."""
    if data[:2] == b"\xff\xd8":
        span = _jpeg_app1(data)
        return data[span[0] : span[1]] if span else b""
    if data[:4] in (b"II*\0", b"MM\0*"):
        return data
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        i = 8
        while i + 8 <= len(data):
            size, kind = struct.unpack(">I4s", data[i : i + 8])
            if kind == b"eXIf":
                return data[i + 8 : i + 8 + size]
            if kind in (b"IDAT", b"IEND"):
                return b""
            i += 12 + size
        return b""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        i = 12
        while i + 8 <= len(data):
            kind, size = struct.unpack("<4sI", data[i : i + 8])
            if kind == b"EXIF":
                block = data[i + 8 : i + 8 + size]
                return block[6:] if block.startswith(b"Exif\0\0") else block
            i += 8 + size + (size & 1)
        return b""
    if data[4:8] == b"ftyp":  # HEIF/AVIF: the Exif item holds "Exif\0\0" + TIFF
        at = data.find(b"Exif\0\0")
        return data[at + 6 :] if at >= 0 else b""
    return b""


# ---------------------------------------------------------------- reading tags
class _Tiff:
    def __init__(self, block: bytes):
        self.b = block
        if block[:2] == b"II":
            self.e = "<"
        elif block[:2] == b"MM":
            self.e = ">"
        else:
            raise ValueError("not TIFF")

    def u16(self, at: int) -> int:
        return struct.unpack(self.e + "H", self.b[at : at + 2])[0]

    def u32(self, at: int) -> int:
        return struct.unpack(self.e + "I", self.b[at : at + 4])[0]

    def entries(self, at: int):
        """(tag, type, count, value offset, entry offset) of one IFD."""
        n = self.u16(at)
        if n > 1000:
            raise ValueError("bad IFD")
        for k in range(n):
            e = at + 2 + 12 * k
            tag, typ, count = struct.unpack(self.e + "HHI", self.b[e : e + 8])
            size = SIZES.get(typ, 1) * count
            yield tag, typ, count, (e + 8 if size <= 4 else self.u32(e + 8)), e

    def value(self, typ: int, count: int, at: int):
        size = SIZES.get(typ, 1) * count
        if at + size > len(self.b) or count > 4096:
            return None
        raw = self.b[at : at + size]
        if typ == 2:
            return raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()
        if typ == 7:
            return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip() if count > 4 else raw
        fmt = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}.get(typ)
        if fmt:
            vals = struct.unpack(self.e + fmt * count, raw)
        elif typ in (5, 10):
            nums = struct.unpack(self.e + ("I" if typ == 5 else "i") * (2 * count), raw)
            vals = tuple(nums[i] / nums[i + 1] if nums[i + 1] else 0.0 for i in range(0, len(nums), 2))
        else:
            return None
        return vals[0] if len(vals) == 1 else vals

    def ifd(self, at: int, names: dict) -> tuple[dict, dict]:
        """({name: value}, {tag: offset of a pointer tag's target})."""
        out, links = {}, {}
        for tag, typ, count, at_value, _ in self.entries(at):
            if tag in (0x8769, 0x8825) and typ in (4, 13):
                links[tag] = self.u32(at_value)
            elif tag in names:
                v = self.value(typ, count, at_value)
                if v not in (None, "", b""):
                    out[names[tag]] = v
        return out, links


def parse(block: bytes) -> dict:
    """Named EXIF values from a TIFF block; {} when it can't be read."""
    try:
        t = _Tiff(block)
        tags, links = t.ifd(t.u32(4), TAGS)
        if 0x8769 in links:
            tags |= t.ifd(links[0x8769], EXIF_TAGS)[0]
        if 0x8825 in links:
            tags |= t.ifd(links[0x8825], GPS_TAGS)[0]
        return tags
    except (ValueError, struct.error, IndexError):
        return {}


def read(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return parse(tiff_block(f.read(HEAD)))
    except OSError:
        return {}


def orientation(path: Path) -> int:
    o = read(path).get("orientation", 1)
    return o if o in ORIENT else 1


def gps(tags: dict) -> tuple[float, float] | None:
    """(latitude, longitude) in signed degrees, when the photo has them."""
    try:
        lat = sum(v / 60**i for i, v in enumerate(tags["lat"]))
        lon = sum(v / 60**i for i, v in enumerate(tags["lon"]))
    except (KeyError, TypeError):
        return None
    if str(tags.get("lat_ref", "N")).upper().startswith("S"):
        lat = -lat
    if str(tags.get("lon_ref", "E")).upper().startswith("W"):
        lon = -lon
    return lat, lon


# ---------------------------------------------------------------- writing the Orientation of a JPEG
def _minimal_app1(orient: int) -> bytes:
    """An Exif APP1 segment holding only an Orientation tag (big-endian TIFF, one IFD)."""
    tiff = (
        b"MM\0*"
        + struct.pack(">I", 8)
        + struct.pack(">H", 1)
        + struct.pack(">HHIHH", 0x0112, 3, 1, orient, 0)
        + struct.pack(">I", 0)
    )
    body = b"Exif\0\0" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body


def set_jpeg_orientation(data: bytes, orient: int) -> bytes:
    """data (a whole JPEG file) with its Orientation tag set to orient; every other byte of the image stays.
    Raises ValueError if it isn't a JPEG we can safely change."""
    if data[:2] != b"\xff\xd8" or orient not in ORIENT:
        raise ValueError("not a JPEG")
    span = _jpeg_app1(data)
    if not span:  # no EXIF yet: add one after SOI (and a JFIF APP0)
        at = 2
        if data[2:4] == b"\xff\xe0":
            at = 4 + struct.unpack(">H", data[4:6])[0]
        return data[:at] + _minimal_app1(orient) + data[at:]
    start, end = span
    t = _Tiff(data[start:end])
    ifd0 = t.u32(4)
    for tag, typ, count, at_value, _ in t.entries(ifd0):
        if tag == 0x0112 and typ == 3 and count == 1:  # patch the two bytes in place
            pos = start + at_value
            return data[:pos] + struct.pack(t.e + "H", orient) + data[pos + 2 :]
    # EXIF without an Orientation tag: append a copy of IFD0 plus the tag at the end of the block and point the
    # header at it. Every other offset in the block stays valid; the old IFD0 is simply no longer used.
    entries = [t.b[e : e + 12] for _, _, _, _, e in t.entries(ifd0)]
    nxt = t.u32(ifd0 + 2 + 12 * len(entries))
    entries.append(struct.pack(t.e + "HHIHH", 0x0112, 3, 1, orient, 0))
    entries.sort(key=lambda raw: struct.unpack(t.e + "H", raw[:2])[0])
    block = bytearray(t.b)
    if len(block) % 2:
        block += b"\0"
    new_at = len(block)
    block += struct.pack(t.e + "H", len(entries)) + b"".join(entries) + struct.pack(t.e + "I", nxt)
    block[4:8] = struct.pack(t.e + "I", new_at)
    seg = b"Exif\0\0" + bytes(block)
    if len(seg) + 2 > 0xFFFF:
        raise ValueError("EXIF block too big")
    app1_start = start - 10  # FF E1, length, "Exif\0\0"
    return data[:app1_start] + b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg + data[end:]


def then(first: int, second: int) -> int:
    """The Orientation value that shows a picture as `first` would, then turned the way `second` turns."""
    a, b, c, d = ORIENT.get(second, ORIENT[1])
    e, f, g, h = ORIENT.get(first, ORIENT[1])
    m = (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)
    return next(k for k, v in ORIENT.items() if v == m)
