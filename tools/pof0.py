"""Reader for the Sega/CRI-style 'DUMY' + data chunk + POF0 pointer table used by some Votoms files.

Layout seen in menu/text.mtt:
  0x00 'DUMY' u32 size(0x10) ...
  0x18 tag(4) u32 size   -> data chunk; pointers inside are relative to DATA_BASE (0x20)
  then 'POF0' u32 size   -> packed list of pointer locations (deltas * 4)
"""
import struct

DATA_BASE = 0x20


def chunks(d):
    out = []
    i = 0
    while i + 8 <= len(d):
        tag = d[i:i + 4]
        size = struct.unpack_from('<I', d, i + 4)[0]
        if not tag.strip(b'\0') or size == 0 and tag == b'\0\0\0\0':
            break
        out.append((tag, i, size))
        if tag == b'POF0' and i > 0x18:
            break
        i += 8 + size
    return out


def pointer_locations(d):
    """Return absolute file offsets of every pointer, decoded from the trailing POF0 chunk."""
    cs = chunks(d)
    data = [c for c in cs if c[1] == 0x18]
    pof = [c for c in cs if c[0] == b'POF0' and c[1] > 0x18]
    if not data or not pof:
        return None
    _, at, size = pof[0]
    p = d[at + 8:at + 8 + size]
    locs = []
    cur = 0
    i = 0
    while i < len(p):
        b = p[i]
        kind = b & 0xC0
        if kind == 0x40:
            v = b & 0x3F; i += 1
        elif kind == 0x80:
            v = ((b & 0x3F) << 8) | p[i + 1]; i += 2
        elif kind == 0xC0:
            v = ((b & 0x3F) << 24) | (p[i + 1] << 16) | (p[i + 2] << 8) | p[i + 3]; i += 4
        else:
            break  # 0x00 = end / padding
        cur += v * 4
        locs.append(DATA_BASE + cur)
    return locs


def data_chunk(d):
    for tag, at, size in chunks(d):
        if at == 0x18:
            return at + 8, at + 8 + size
    return None
