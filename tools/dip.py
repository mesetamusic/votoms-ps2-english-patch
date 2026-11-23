"""Parser/extractor for Votoms _DATA.DIP archive (reverse-engineered)."""
import struct, sys, os, collections

def parse(path):
    f = open(path, 'rb')
    hdr = f.read(0x20)
    ent_len, name_len, total, ent_start, name_off, data_off = struct.unpack_from('<6I', hdr)
    f.seek(name_off); names_raw = f.read(name_len)
    names = [names_raw[i:i+32].split(b'\0')[0].decode('ascii', 'replace') for i in range(0, name_len, 32)]
    f.seek(ent_start); raw = f.read(ent_len)
    ents = [struct.unpack_from('<HHII', raw, i) for i in range(0, len(raw) - 11, 12)]
    files = []
    def walk(idx, prefix):
        flag, ni, a, b = ents[idx]
        if flag == 0:
            p = prefix + names[ni] + '/'
            for c in range(b, b + a):
                walk(c, p)
        else:
            files.append((prefix + names[ni], data_off + b, a * 32))
    walk(0, '')
    return f, files, hdr

if __name__ == '__main__':
    f, files, hdr = parse(sys.argv[1])
    print('header', [hex(x) for x in struct.unpack('<8I', hdr)])
    print('files', len(files))
    ext = collections.Counter()
    sz = collections.Counter()
    for p, o, s in files:
        e = os.path.splitext(p)[1]; ext[e] += 1; sz[e] += s
    for e, n in ext.most_common():
        print(f'{e:8} {n:5} {sz[e]/1e6:8.1f} MB')
    dirs = collections.Counter(p.rsplit('/', 1)[0] for p, o, s in files)
    for d, n in sorted(dirs.items()):
        print(d, n)
    if len(sys.argv) > 2:
        out = sys.argv[2]
        for p, o, s in files:
            dst = os.path.join(out, p); os.makedirs(os.path.dirname(dst), exist_ok=True)
            f.seek(o); open(dst, 'wb').write(f.read(s))
        print('extracted')
