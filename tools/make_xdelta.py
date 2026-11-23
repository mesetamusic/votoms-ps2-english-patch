"""Create / apply a standard VCDIFF (RFC 3284) patch, the format xdelta3 uses.

The English patch never changes the ISO size, so the delta is simple: the ISO is
split into 1 MiB windows; each window copies the matching range of the original
ISO and only the changed bytes are stored (ADD). The output opens in xdelta3,
Delta Patcher, xdelta UI and other VCDIFF tools.

usage:
  python make_xdelta.py make  <original.iso> <patched.iso> <out.xdelta>
  python make_xdelta.py apply <original.iso> <patch.xdelta> <out.iso>
"""
import sys, hashlib, zlib

WIN = 1 << 20
SECTOR = 2048
MIN_GAP = 16  # unchanged runs shorter than this are folded into the ADD


def varint(n):
    out = [n & 0x7f]; n >>= 7
    while n:
        out.append(0x80 | (n & 0x7f)); n >>= 7
    return bytes(reversed(out))


def diff_ranges(a, b):
    """[(start, end)] byte ranges where a and b differ (a, b same length)."""
    ranges = []
    for s in range(0, len(a), SECTOR):
        if a[s:s + SECTOR] == b[s:s + SECTOR]: continue
        e = min(len(a), s + SECTOR); i = s
        while i < e:
            if a[i] != b[i]:
                j = i
                while j < e and a[j] != b[j]: j += 1
                if ranges and i - ranges[-1][1] < MIN_GAP: ranges[-1][1] = j
                else: ranges.append([i, j])
                i = j
            else:
                i += 1
    return ranges


def window(pos, a, b):
    n = len(b); data = bytearray(); inst = bytearray(); addr = bytearray(); at = 0
    def copy(off, ln):
        inst.append(19); inst.extend(varint(ln)); addr.extend(varint(off))   # COPY, mode VCD_SELF
    for s, e in diff_ranges(a, b):
        if s > at: copy(at, s - at)
        inst.append(1); inst.extend(varint(e - s)); data.extend(b[s:e])      # ADD
        at = e
    if at < n: copy(at, n - at)
    body = (varint(n) + b'\0' + varint(len(data)) + varint(len(inst)) + varint(len(addr))
            + bytes(data) + bytes(inst) + bytes(addr))
    return b'\x01' + varint(len(a)) + varint(pos) + varint(len(body)) + body   # VCD_SOURCE


def make(orig, new, out):
    with open(orig, 'rb') as fa, open(new, 'rb') as fb, open(out, 'wb') as fo:
        fo.write(b'\xd6\xc3\xc4\x00\x00')
        pos = 0
        while True:
            a = fa.read(WIN); b = fb.read(WIN)
            if not b: break
            assert len(a) == len(b), 'ISOs differ in size'
            fo.write(window(pos, a, b)); pos += len(b)
        assert not fa.read(1), 'ISOs differ in size'


# ---------------------------------------------------------------- decoder (full RFC 3284 default code table)
def code_table():
    t = [(('RUN', 0, 0), None)] + [(('ADD', s, 0), None) for s in range(18)]
    for m in range(9):
        t.append((('CPY', 0, m), None))
        t += [(('CPY', s, m), None) for s in range(4, 19)]
    for m in range(6):
        for a in range(1, 5):
            for c in range(4, 7): t.append((('ADD', a, 0), ('CPY', c, m)))
    for m in range(6, 9):
        for a in range(1, 5): t.append((('ADD', a, 0), ('CPY', 4, m)))
    for m in range(9): t.append((('CPY', 4, m), ('ADD', 1, 0)))
    assert len(t) == 256
    return t


class R:
    def __init__(s, d, p=0): s.d, s.p = d, p
    def byte(s): s.p += 1; return s.d[s.p - 1]
    def int(s):
        n = 0
        while True:
            c = s.byte(); n = (n << 7) | (c & 0x7f)
            if not c & 0x80: return n
    def take(s, n): s.p += n; return s.d[s.p - n:s.p]


def apply(orig, patch, out):
    table = code_table()
    d = open(patch, 'rb').read(); r = R(d)
    assert r.take(4) == b'\xd6\xc3\xc4\x00', 'not a VCDIFF file'
    hi = r.byte()
    assert not hi & 3, 'secondary compression / custom code tables are not supported'
    if hi & 4: r.take(r.int())
    with open(orig, 'rb') as fs, open(out, 'wb') as fo:
        while r.p < len(d):
            wi = r.byte(); src = b''
            if wi & 3:
                assert wi & 1, 'target-referenced windows not supported'
                ln = r.int(); ps = r.int(); fs.seek(ps); src = fs.read(ln)
            r.int(); tlen = r.int(); assert r.byte() == 0
            dl, il, al = r.int(), r.int(), r.int()
            if wi & 4: r.take(4)
            data = R(r.take(dl)); inst = R(r.take(il)); adr = R(r.take(al))
            tgt = bytearray(); near = [0] * 4; ni = 0; same = [0] * 768
            while inst.p < len(inst.d):
                for op in table[inst.byte()]:
                    if op is None: continue
                    kind, size, mode = op
                    if size == 0: size = inst.int()
                    if kind == 'ADD': tgt += data.take(size)
                    elif kind == 'RUN': tgt += data.take(1) * size
                    else:
                        here = len(src) + len(tgt)
                        if mode == 0: a = adr.int()
                        elif mode == 1: a = here - adr.int()
                        elif mode < 6: a = near[mode - 2] + adr.int()
                        else: a = same[(mode - 6) * 256 + adr.byte()]
                        near[ni] = a; ni = (ni + 1) % 4; same[a % 768] = a
                        for k in range(size):
                            q = a + k
                            tgt.append(src[q] if q < len(src) else tgt[q - len(src)])
            assert len(tgt) == tlen
            fo.write(tgt)


def hashes(path):
    md5, sha1, crc = hashlib.md5(), hashlib.sha1(), 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b: break
            md5.update(b); sha1.update(b); crc = zlib.crc32(b, crc)
    return f'{crc & 0xffffffff:08X}', md5.hexdigest(), sha1.hexdigest()


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make': make(*sys.argv[2:5])
    elif cmd == 'apply': apply(*sys.argv[2:5])
    elif cmd == 'hash': print(*hashes(sys.argv[2]))
    else: sys.exit(__doc__)
