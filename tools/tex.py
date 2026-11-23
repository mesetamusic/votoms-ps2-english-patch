"""RTX3 texture containers (.tex) used by the menus: decode to PNG and re-encode."""
import struct, zlib, sys, os

def entries(d):
    n = struct.unpack_from('<I', d, 0)[0]
    out = []
    for i in range(n):
        o = 0x10 + i * 32
        name = d[o:o + 16].split(b'\0')[0].decode('ascii', 'replace')
        size, off = struct.unpack_from('<II', d, o + 20)
        out.append((name, off, size))
    return out

def header(d, off):
    """(psm, w, h, data_offset) for an RTX3 or single-picture TIM2 texture."""
    if d[off:off + 4] == b'TIM2':
        p = off + 0x10
        hsize = struct.unpack_from('<H', d, p + 0x0c)[0]
        itype = d[p + 0x13]
        w, h = struct.unpack_from('<HH', d, p + 0x14)
        return {4: 0x14, 5: 0x13}[itype], w, h, p + hsize
    assert d[off:off + 4] == b'RTX3', d[off:off + 4]
    psm = struct.unpack_from('<I', d, off + 0x1c)[0]
    w, h = struct.unpack_from('<HH', d, off + 0x20)
    return psm, w, h, off + 0x40

def csm1(i):  # PS2 8-bit CLUT index swizzle
    return (i & ~0x18) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)

def decode(d, off):
    psm, w, h, data = header(d, off)
    bpp = {0x14: 4, 0x13: 8}[psm]
    n = w * h * bpp // 8
    ncol = 16 if bpp == 4 else 256
    pal_raw = [struct.unpack_from('<4B', d, data + n + 4 * i) for i in range(ncol)]
    pal = pal_raw if bpp == 4 else [pal_raw[csm1(i)] for i in range(256)]
    idx = bytearray(w * h)
    if bpp == 4:
        for i in range(n):
            b = d[data + i]
            idx[2 * i] = b & 15; idx[2 * i + 1] = b >> 4
    else:
        idx[:] = d[data:data + n]
    return dict(psm=psm, w=w, h=h, bpp=bpp, idx=idx, pal=pal, data=data, n=n)

def write_png(path, w, h, rgba):
    raw = b''.join(b'\0' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))

def to_rgba(t, opaque=True):
    out = bytearray(t['w'] * t['h'] * 4)
    for i, c in enumerate(t['idx']):
        r, g, b, a = t['pal'][c]
        out[4 * i:4 * i + 4] = bytes((r, g, b, 255 if opaque else min(255, a * 2)))
    return out

if __name__ == '__main__':
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    d = open(src, 'rb').read()
    base = os.path.splitext(os.path.basename(src))[0]
    for name, off, size in entries(d):
        try:
            t = decode(d, off)
        except Exception as e:
            print(name, 'skip', e); continue
        write_png(os.path.join(outdir, f'{base}_{name}.png'), t['w'], t['h'], to_rgba(t, opaque=False))
        print(name, hex(off), t['w'], t['h'], t['bpp'])

def read_png(path):
    """Minimal PNG reader (8-bit RGBA or RGB, all filter types)."""
    d = open(path, 'rb').read(); i = 8; idat = b''
    while i < len(d):
        n, t = struct.unpack_from('>I4s', d, i); b = d[i + 8:i + 8 + n]
        if t == b'IHDR':
            w, h, depth, ctype = struct.unpack_from('>IIBB', b)
            assert depth == 8 and ctype in (2, 6), (depth, ctype)
        if t == b'IDAT': idat += b
        i += 12 + n
    bpp = 4 if ctype == 6 else 3
    raw = zlib.decompress(idat); stride = w * bpp
    out = bytearray(); prev = bytearray(stride); p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p + 1:p + 1 + stride]); p += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += line if bpp == 4 else b''.join(bytes(line[k:k + 3]) + b'\xff' for k in range(0, stride, 3))
        prev = line
    return w, h, out

def blobs(t, gapx=4, gapy=1, thresh=8):
    w, h = t['w'], t['h']
    on = [t['pal'][c][3] > thresh for c in t['idx']]
    seen = bytearray(w * h); out = []
    for s in range(w * h):
        if not on[s] or seen[s]: continue
        stack = [s]; seen[s] = 1; x0 = x1 = s % w; y0 = y1 = s // w
        while stack:
            q = stack.pop(); qx, qy = q % w, q // w
            x0, x1, y0, y1 = min(x0, qx), max(x1, qx), min(y0, qy), max(y1, qy)
            for dy in range(-gapy, gapy + 1):
                for dx in range(-gapx, gapx + 1):
                    nx, ny = qx + dx, qy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        r = ny * w + nx
                        if on[r] and not seen[r]: seen[r] = 1; stack.append(r)
        out.append((x0, y0, x1 - x0 + 1, y1 - y0 + 1))
    return out

def crop_png(t, rect, path, scale=4):
    x0, y0, cw, ch = rect; w = t['w']
    rgba = bytearray(cw * scale * ch * scale * 4)
    for y in range(ch * scale):
        for x in range(cw * scale):
            r, g, b, a = t['pal'][t['idx'][(y0 + y // scale) * w + x0 + x // scale]]
            a = min(255, a * 2); j = (y * cw * scale + x) * 4
            rgba[j:j + 4] = bytes((r * a // 255 + 60 * (255 - a) // 255, g * a // 255 + 30 * (255 - a) // 255, b * a // 255 + 90 * (255 - a) // 255, 255))
    write_png(path, cw * scale, ch * scale, rgba)

def tight(t, win, thresh=8):
    x0, y0, ww, wh = win; w = t['w']
    xs, ys = [], []
    for y in range(y0, y0 + wh):
        for x in range(x0, x0 + ww):
            if t['pal'][t['idx'][y * w + x]][3] > thresh: xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) if xs else None
