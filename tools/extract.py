"""Extract every Japanese string from the unpacked Votoms data into a translation sheet.

Usage: python extract.py <dip_root_dir> <SLPS_258.27> <out_dir>

Writes:
  out_dir/strings.json   every occurrence: file, offset, room, mode
  out_dir/sheet.tsv      one row per unique Japanese string (id, max line bytes, lines, jp)
"""
import json, os, re, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pof0

KANA = lambda c: '぀' <= c <= 'ヿ'
JPCH = lambda c: KANA(c) or '一' <= c <= '鿿' or '＀' <= c <= '｠' or '￠' <= c <= '￯' or '　' <= c <= '〿'

# Files whose text we never touch (graphics/model/audio formats where hits are coincidental)
SKIP_EXT = {'.atp', '.mt4', '.tex', '.txc', '.snd', '.acx', '.ypc', '.bd', '.ico', '.fnt', '.fdb', '.ai', '.aud', '.pdp'}


def valid_text(b, strict=False, heur=False):
    """Decode a candidate string; return str or None if it doesn't look like game text.
    strict: used for unaligned heuristic hits, needs more kana to rule out binary noise."""
    if len(b) < 4:
        return None
    try:
        s = b.decode('cp932')
    except UnicodeDecodeError:
        return None
    if any(not (JPCH(c) or ' ' <= c <= '~' or c == '\n' or '‐' <= c <= '♯' or c in '¥§¨°±´¶×÷' or 'Α' <= c <= 'ё') for c in s):
        return None
    kana = sum(KANA(c) for c in s)
    jp = sum(JPCH(c) for c in s)
    if jp < 2 or (strict and kana < 3):
        return None
    if heur and (kana < 1 or re.search(r'([^぀-ヿ　…ー－―])', s)):
        return None
    if heur:
        if jp < 3 and not all(KANA(c) for c in s):
            return None
        if s[0] in 'ャュョァィゥェォッゃゅょっ÷':
            return None
    # mostly-Japanese requirement (allow control codes like @c06, %s, numbers)
    if jp < 0.5 * len(s.replace('\n', '').replace(' ', '')):
        return None
    return s


def room_after(d, start, end, limit):
    """Bytes available for text (excluding terminator): original + trailing zeros up to
    the last 4-byte boundary before the next non-zero byte."""
    j = end + 1  # first byte after terminator
    while j < limit and d[j] == 0:
        j += 1
    if j < limit:
        j &= ~3
    return max(end - start, j - 1 - start)


def scan_heuristic(d):
    """Null-delimited strings anywhere in the file.
    Aligned strings preceded by a zero byte are accepted with normal checks;
    anything else needs to look strongly like text. Leading filler (0xCD runs,
    1-2 stray ASCII/half-width bytes) is skipped."""
    out = []
    n = len(d)
    segs = []
    i = 0
    while i < n:
        if d[i] == 0:
            i += 1
            continue
        j = d.find(b'\0', i, n)
        if j < 0:
            j = n
        st = i
        while st < j and d[st] == 0xCD:
            st += 1
        segs.append((st, j))
        i = j + 1
    # Some files pack strings on 4-byte boundaries with 1-3 garbage filler bytes in
    # front; others (fixed records like string.dat) start text at any offset.
    good = [st for st, j in segs if j - st >= 8 and valid_text(d[st:j], heur=True)]
    aligned_layout = bool(good) and sum(st % 4 == 0 for st in good) >= 0.7 * len(good)
    for st, j in segs:
        ca = (st + 3) & ~3
        cands = [ca, st] if aligned_layout and ca != st else [st]
        for c in cands:
            if c >= j or d[c] < 0x80:
                continue
            aligned = c % 4 == 0 and (c == 0 or d[c - 1] == 0 or c != st)
            s_ = valid_text(d[c:j], strict=not aligned, heur=True)
            if s_ is not None:
                out.append((c, j, s_, 'heur'))
                break
    return out


def scan_pof0(d):
    locs = pof0.pointer_locations(d)
    if not locs:
        return None
    lo, hi = pof0.data_chunk(d)
    out = []
    seen = set()
    for l in locs:
        t = struct.unpack_from('<I', d, l)[0] + pof0.DATA_BASE
        if t in seen or not (lo <= t < hi):
            continue
        j = d.find(b'\0', t, hi)
        if j < 0:
            continue
        s = valid_text(d[t:j])
        if s is not None:
            seen.add(t)
            out.append((t, j, s, 'pool'))
    return out


def walk(root):
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f)
            yield os.path.relpath(p, os.path.dirname(root)).replace('\\', '/'), p


def main(root, elf, outdir):
    os.makedirs(outdir, exist_ok=True)
    occ = []
    datas = {}
    files = list(walk(root)) + [('ELF', elf)]
    for rel, p in sorted(files):
        if os.path.splitext(rel)[1].lower() in SKIP_EXT:
            continue
        d = open(p, 'rb').read()
        found = scan_pof0(d) if d[:4] == b'DUMY' else None
        if found is None:
            found = scan_heuristic(d)
        for st, en, s, mode in found:
            room = en - st if mode == 'pool' else room_after(d, st, en, len(d))
            if mode != 'pool' and st % 4 == 0:
                room = max(room, ((en + 1 + 3) & ~3) - 1 - st)  # filler up to next aligned slot
            occ.append(dict(file=rel, off=st, len=en - st, room=room, mode=mode, jp=s))
        if any(o['file'] == rel and o['mode'] == 'heur' for o in occ[-len(found):] if found):
            datas[rel] = d
    # Fix starts where the aligned guess cut off real leading characters: if the bytes
    # just before the string extend it into a string seen elsewhere, use that.
    count = {}
    for o in occ:
        count[o['jp']] = count.get(o['jp'], 0) + 1
    for o in occ:
        if o['mode'] != 'heur':
            continue
        d = datas[o['file']]
        best = None
        for k in (1, 2, 3):
            st = o['off'] - k
            if st < 0 or d[st] == 0:
                break
            try:
                s = d[st:o['off'] + o['len']].decode('cp932')
            except UnicodeDecodeError:
                continue
            if s != o['jp'] and s.endswith(o['jp']) and count.get(s, 0) > 0:
                if best is None or count[s] > count[best[1]]:
                    best = (st, s)
        if best:
            st, s = best
            en = o['off'] + o['len']
            o.update(off=st, len=en - st, jp=s, room=max(o['room'] + (o['off'] - st), en - st))
            continue
        # Or the other way: 1-3 filler bytes in front of a string seen elsewhere.
        if count.get(o['jp'], 0) == 1:
            for k in (1, 2, 3):
                try:
                    s = d[o['off'] + k:o['off'] + o['len']].decode('cp932')
                except UnicodeDecodeError:
                    continue
                if count.get(s, 0) > 0:
                    o.update(off=o['off'] + k, len=o['len'] - k, jp=s, room=o['room'] - k)
                    break
    # Known one-off filler bytes in front of tutorial strings (hud/tuto.pac)
    for o in occ:
        for pre in ('）左下の', 'ら敵の背後', '乗Ｌ１'):
            if o['jp'].startswith(pre) and o['off'] % 4 == 2:
                o.update(off=o['off'] + 2, len=o['len'] - 2, jp=o['jp'][1:], room=o['room'] - 2)
    uniq = {}
    for o in occ:
        uniq.setdefault(o['jp'], []).append(o)
    json.dump(occ, open(os.path.join(outdir, 'strings.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(outdir, 'sheet.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\tfiles\tlines\twidth\troom\tjp\n')
        for n, (s, os_) in enumerate(uniq.items()):
            lines = s.split('\n')
            width = max(len(x.encode('cp932')) for x in lines)
            room = min(o['room'] for o in os_ if o['mode'] != 'pool') if any(o['mode'] != 'pool' for o in os_) else -1
            fl = ','.join(sorted(set(o['file'] for o in os_)))
            f.write(f"{n}\t{fl}\t{len(lines)}\t{width}\t{room}\t{s.replace(chr(10), '|')}\n")
    by = {}
    for o in occ:
        by[o['file']] = by.get(o['file'], 0) + 1
    for k, v in sorted(by.items(), key=lambda x: -x[1]):
        print(f'{v:6} {k}')
    print('occurrences', len(occ), 'unique', len(uniq))


if __name__ == '__main__':
    main(*sys.argv[1:4])
