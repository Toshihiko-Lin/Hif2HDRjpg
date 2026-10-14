"""Copy opaque EXIF without relocating MakerNote offsets or re-encoding JPEGs.

EXIF is inserted before the MPF marker. MPF-relative secondary offsets therefore
remain unchanged; only the primary MPEntry size increases. See the CIPA MPF
layout and https://developer.android.com/media/platform/hdr-image-format .
"""
import struct


def jpeg_segments(data: bytes):
    """Yield (marker, marker_start, payload_start, segment_end) before SOS."""
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("无效的 JPEG 文件头。")
    position = 2
    while position + 4 <= len(data):
        if data[position] != 255:
            raise ValueError("JPEG 段边界无效。")
        marker = data[position + 1]
        if marker in (0xDA, 0xD9):
            return
        length = int.from_bytes(data[position + 2:position + 4], "big")
        end = position + 2 + length
        if length < 2 or end > len(data):
            raise ValueError("JPEG 段长度无效。")
        yield marker, position, position + 4, end
        position = end
    raise ValueError("JPEG 缺少扫描数据。")


def tiff_header(data: bytes | bytearray, base: int, end: int):
    if base + 8 > end:
        raise ValueError("TIFF 文件头不完整。")
    endian = {b"II": "<", b"MM": ">"}.get(bytes(data[base:base + 2]))
    if not endian or struct.unpack_from(endian + "H", data, base + 2)[0] != 42:
        raise ValueError("不支持的 EXIF/MPF TIFF 文件头。")
    offset = struct.unpack_from(endian + "I", data, base + 4)[0]
    return endian, base + offset


def ifd_entries(data, base, start, end, endian):
    if start < base + 8 or start + 2 > end:
        raise ValueError("IFD 指针越界。")
    count = struct.unpack_from(endian + "H", data, start)[0]
    if start + 2 + count * 12 + 4 > end:
        raise ValueError("IFD 数据不完整。")
    for pos in range(start + 2, start + 2 + count * 12, 12):
        tag, kind, count = struct.unpack_from(endian + "HHI", data, pos)
        yield tag, kind, count, pos + 8


def normalized_exif(exif: bytes, size: tuple[int, int]) -> bytes:
    """Patch existing scalar orientation/dimensions; all other bytes stay put."""
    if not exif.startswith(b"Exif\x00\x00"):
        raise ValueError("源照片的 EXIF 数据头无效，已拒绝静默丢弃。")
    if len(exif) > 65533:
        raise ValueError("源 EXIF 超过 JPEG 单段 65533 字节限制，无法完整复制。")
    data = bytearray(exif)
    base, end = 6, len(data)
    endian, first = tiff_header(data, base, end)
    exif_ifd = None

    def patch(entries, values):
        nonlocal exif_ifd
        for tag, kind, count, field in entries:
            if tag == 0x8769 and kind == 4 and count == 1:
                exif_ifd = base + struct.unpack_from(endian + "I", data, field)[0]
            if tag in values and count == 1 and kind in (3, 4):
                struct.pack_into(endian + ("H" if kind == 3 else "I"), data, field, values[tag])

    patch(ifd_entries(data, base, first, end, endian),
          {0x112: 1, 0x100: size[0], 0x101: size[1]})
    if exif_ifd:
        patch(ifd_entries(data, base, exif_ifd, end, endian),
              {0xA002: size[0], 0xA003: size[1]})
    return bytes(data)


def mpf_index(data: bytes):
    """Return primary size field, endian, and validated (absolute_start, size)."""
    for marker, _, payload, end in jpeg_segments(data):
        if marker != 0xE2 or data[payload:payload + 4] != b"MPF\x00":
            continue
        base = payload + 4
        endian, first = tiff_header(data, base, end)
        for tag, kind, count, field in ifd_entries(data, base, first, end, endian):
            if tag != 0xB002:
                continue
            if kind != 7 or count < 32 or count % 16:
                raise ValueError("不支持的 MPF 图像索引。")
            table = base + struct.unpack_from(endian + "I", data, field)[0]
            if table < base + 8 or table + count > end:
                raise ValueError("MPF 图像表越界。")
            images = []
            for index in range(count // 16):
                _, length, offset = struct.unpack_from(endian + "III", data, table + index * 16)
                start = 0 if index == 0 and offset == 0 else base + offset
                if not length or start + length > len(data) or data[start:start + 2] != b"\xff\xd8":
                    raise ValueError("MPF 图像指针无效。")
                images.append((start, length))
            if images[0][0] != 0 or images[0][1] != images[1][0]:
                raise ValueError("不支持的主图与增益图布局。")
            return table + 4, endian, images
    raise ValueError("JPEG 缺少 MPF 增益图索引。")


def copy_exif(jpeg: bytes, exif: bytes | None, size: tuple[int, int]) -> bytes:
    if not exif:
        return jpeg
    exif = normalized_exif(exif, size)
    primary_size_field, endian, images = mpf_index(jpeg)
    insertion = 2
    for marker, start, payload, end in jpeg_segments(jpeg):
        if marker == 0xE1 and jpeg[payload:payload + 6] == b"Exif\x00\x00":
            raise ValueError("编码结果已含 EXIF，拒绝重复插入。")
        if start == 2 and marker == 0xE0:  # keep JFIF's APP0 immediately after SOI
            insertion = end
    segment = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    delta = len(segment)
    if insertion >= primary_size_field:
        raise ValueError("EXIF 插入点必须位于 MPF 索引之前。")
    result = bytearray(jpeg[:insertion] + segment + jpeg[insertion:])
    struct.pack_into(endian + "I", result, primary_size_field + delta, images[0][1] + delta)
    result = bytes(result)
    _, _, updated = mpf_index(result)
    # Check gain maps verbatim, not just the presence of a signature.
    for (old_start, old_size), (new_start, new_size) in zip(images[1:], updated[1:]):
        if old_size != new_size or jpeg[old_start:old_start + old_size] != result[new_start:new_start + new_size]:
            raise ValueError("EXIF 复制后增益图发生变化，已拒绝保存。")
    return result
