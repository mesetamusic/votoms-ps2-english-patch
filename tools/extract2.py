"""Second extraction pass: whole null-terminated strings that contain Japanese
and are not covered by any frozen occurrence (strings with ASCII prefixes such
as @c02%s@c07, button glyphs or "PlayStation 2" that the first pass cut)."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(__file__))
from extract import SKIP_EXT, JPCH, KANA, room_after
W = os.path.join(os.path.dirname(__file__), '..', 'work')

def allowed(c):
    return (JPCH(c) or '‐' <= c <= '⁯' or 'Ⅰ' <= c <= '⇿'
            or '①' <= c <= '⓿' or '■' <= c <= '⛿' or c in '§¨°±´¶×÷')

def segments(d):
    """Runs of plain Shift-JIS text that end in a NUL byte."""
    i, n, st = 0, len(d), None
    while i < n:
        c = d[i]
        if c == 0:
            if st is not None and i - st >= 4:
                yield st, i
            st = None; i += 1; continue
        if c == 10 or 32 <= c < 127:
            if st is None: st = i
            i += 1; continue
        if (0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc) and i + 1 < n:
            try:
                ch = d[i:i + 2].decode('cp932')
            except UnicodeDecodeError:
                ch = None
            if ch and allowed(ch):
                if st is None: st = i
                i += 2; continue
        st = None; i += 1

def candidates(d, covered):
    out = []
    for st, en in segments(d):
        if any(covered.get(i) for i in range(st, en)):
            continue
        t = d[st:en].decode('cp932')
        jp = [c for c in t if JPCH(c)]
        if sum(KANA(c) for c in t) < 2 or len(jp) < 3:
            continue
        if re.search(r'(.)', t):
            continue
        out.append((st, en, t))
    return out

def main(root, elf):
    occ = json.load(open(os.path.join(W, 'strings_frozen.json'), encoding='utf-8'))
    cov = {}
    for o in occ:
        c = cov.setdefault(o['file'], {})
        for i in range(o['off'], o['off'] + o['len']):
            c[i] = True
    files = [('ELF', elf)]
    base = os.path.dirname(root)
    for dp, _, fs in os.walk(root):
        for f in fs:
            if os.path.splitext(f)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dp, f)
            files.append((os.path.relpath(p, base).replace(os.sep, '/'), p))
    new = []
    for name, p in sorted(files):
        d = open(p, 'rb').read()
        for st, en, t in candidates(d, cov.get(name, {})):
            room = room_after(d, st, en, len(d))
            new.append(dict(file=name, off=st, len=en - st, room=room, mode='heur', jp=t))
    return new

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    new = main(sys.argv[1], sys.argv[2])
    uniq = {}
    for o in new:
        uniq.setdefault(o['jp'], []).append(o['file'])
    print(len(new), 'occurrences', len(uniq), 'unique')
    json.dump(new, open(os.path.join(W, 'extra_candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    for t, fs in list(uniq.items()):
        print(sorted(set(fs))[0], len(fs), t.replace('\n', '|')[:70])
