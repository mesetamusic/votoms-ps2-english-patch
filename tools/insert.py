"""Insert English translations into Votoms game files and build a patched ISO.

Usage:
  python insert.py check  <dip_root> <elf>                 # validate only, write work/report.txt
  python insert.py build  <dip_root> <elf> <iso_in> <iso_out>

Translation files: work/en/*.tsv, lines of  id <TAB> jp-check <TAB> english
  english '='        leave the Japanese string untouched
  '|'                forced line break (each segment is still word-wrapped)
  '{keepN}' prefix   keep the first N Japanese characters (filler bytes before the real string)

Fitting rules:
  * 'heur' strings are rewritten in place and must fit their room (original bytes
    plus zero/filler padding after them).
  * 'pool' strings (menu/text.mtt) are repacked: the whole string pool is rebuilt
    and every pointer to it is updated, so only the total size matters.
"""
import glob, json, os, shutil, struct, sys, textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pof0
from patch_test import iso_find, dip_index

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(HERE, 'work')
MIN_WRAP = 24


def load_sheet():
    rows = {}
    with open(os.path.join(WORK, 'sheet_frozen.tsv'), encoding='utf-8') as f:
        next(f)
        for line in f:
            id_, files, lines, width, room, jp = line.rstrip('\n').split('\t')
            rows[int(id_)] = dict(jp=jp.replace('|', '\n'), lines=int(lines), width=int(width))
    return rows


def load_en(sheet, problems):
    en = {}
    for p in sorted(glob.glob(os.path.join(WORK, 'en', '*.tsv'))):
        for n, line in enumerate(open(p, encoding='utf-8'), 1):
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) != 3:
                problems.append(f'{os.path.basename(p)}:{n}: bad line')
                continue
            id_, chk, text = int(parts[0]), parts[1], parts[2]
            if id_ not in sheet:
                problems.append(f'{os.path.basename(p)}:{n}: unknown id {id_}')
                continue
            if not sheet[id_]['jp'].replace('\n', '|').startswith(chk):
                problems.append(f'{os.path.basename(p)}:{n}: id {id_} check "{chk}" != "{sheet[id_]["jp"][:4]}"')
                continue
            en[sheet[id_]['jp']] = (id_, text)
    return en


def render_all(jp, text, width_orig):
    """'long~~short' gives fallbacks for tight slots; returns a list of (bytes, lines)."""
    return [render(jp, alt, width_orig) for alt in text.split('~~')]


def render(jp, text, width_orig):
    """Return (bytes_without_terminator, lines) for one translation."""
    keep = b''
    if text.startswith('{keep'):
        k = int(text[5:text.index('}')])
        keep = jp[:k].encode('cp932')
        text = text[text.index('}') + 1:]
    text = (text.replace('’', "'").replace('‘', "'").replace('“', '"')
            .replace('”', '"').replace('…', '...').replace('—', '-'))
    multiline = '\n' in jp or '|' in text
    out = []
    for seg in text.split('|'):
        if multiline and seg:
            w = max(width_orig, MIN_WRAP)
            out.extend(textwrap.wrap(seg, w, break_long_words=False, break_on_hyphens=False) or [''])
        else:
            out.append(seg)
    s = '\n'.join(out)
    return keep + s.encode('ascii'), out


def plan(dip_root, elf, problems, report):
    sheet = load_sheet()
    en = load_en(sheet, problems)
    occ = json.load(open(os.path.join(WORK, 'strings_frozen.json'), encoding='utf-8'))
    rendered = {}
    for jp, (id_, text) in en.items():
        if text == '=':
            continue
        if text.startswith('{keep') and text.endswith('}'):
            continue
        try:
            rendered[jp] = render_all(jp, text, sheet[id_]['width'])
        except UnicodeEncodeError as e:
            problems.append(f'id {id_}: non-ASCII character in English: {e}')
    edits = {}  # file -> list of (occurrence, new bytes)
    over = 0
    seen_over = set()
    for o in occ:
        alts = rendered.get(o['jp'])
        if alts is None:
            continue
        b, lines = alts[0]
        if o['mode'] != 'pool':
            for b2, l2 in alts:
                if len(b2) <= o['room']:
                    b, lines = b2, l2
                    break
        if o['mode'] != 'pool' and len(b) > o['room']:
            over += 1
            id_ = en[o['jp']][0]
            if id_ not in seen_over:
                seen_over.add(id_)
                problems.append(f'id {id_}: {len(b)} bytes > room {o["room"]} in {o["file"]}: {b[:60]!r}')
            continue
        edits.setdefault(o['file'], []).append((o, b))
    for jp, (id_, text) in en.items():
        if jp in rendered:
            lines = rendered[jp][0][1]
            if len(lines) > sheet[id_]['lines'] + 1 and sheet[id_]['lines'] > 1:
                report.append(f'id {id_}: {len(lines)} lines (JP had {sheet[id_]["lines"]})')
    missing = [i for i, r in sheet.items() if r['jp'] not in en]
    report.append(f'translated {len(en)} / {len(sheet)} unique strings; {len(missing)} untranslated; {over} occurrences too long')
    return edits


def apply_heur(d, items):
    d = bytearray(d)
    for o, b in items:
        st = o['off']
        # clear the old string (keep everything past its own terminator except padding we use)
        d[st:st + o['len']] = b'\0' * o['len']
        d[st:st + len(b)] = b
        d[st + len(b)] = 0
    return bytes(d)


def apply_pool(d, items, problems, name):
    """Rewrite pointer-referenced strings of a DUMY/POF0 file.

    Each translated string owns a 'slot': its original bytes plus the filler up to
    the next 4-byte boundary (where the next string starts). Strings that fit are
    written in place; the rest are moved into space freed by strings that shrank,
    and every pointer to them is updated."""
    d = bytearray(d)
    locs = pof0.pointer_locations(bytes(d))
    by_target = {}
    for l in locs:
        t = struct.unpack_from('<I', d, l)[0] + pof0.DATA_BASE
        by_target.setdefault(t, []).append(l)
    ptr_bytes = set()
    for l in locs:
        ptr_bytes.update(range(l, l + 4))
    targets = sorted(by_target)
    new_text = {o['off']: b for o, b in items}
    slots = {}
    for o, _ in items:
        t = o['off']
        end = ((t + o['len'] + 1) + 3) & ~3
        # never let a slot run into another pointer target or a pointer field
        for u in targets:
            if t < u < end:
                end = u
        end = min([end] + [b for b in range(t, end) if b in ptr_bytes])
        inner = [u for u in targets if t < u < t + o['len']]
        if inner:
            problems.append(f'{name}: pointer into the middle of string at {t:#x}, skipped')
            continue
        slots[t] = end
    def data_of(t, failed):
        return items_original(items, t) if t in failed else new_text[t] + b'\0'

    def align(x):
        return (x + 3) & ~3

    # contiguous runs of slots: inside a run the strings can be packed tightly,
    # which merges the per-string slack into one free block at the run's end
    runs = []
    for t, end in sorted(slots.items()):
        if runs and runs[-1][1] == t:
            runs[-1][1] = end
            runs[-1][2].append(t)
        else:
            runs.append([t, end, [t]])

    def allocate(failed):
        pos, free, pending = {}, [], []
        for start, end, ts in runs:
            keep = list(ts)
            while True:
                size = 0
                for t in keep:
                    size = align(size) + len(data_of(t, failed))
                if start + size <= end:
                    break
                worst = max(keep, key=lambda t: len(data_of(t, failed)))
                keep.remove(worst)
                pending.append(worst)
            at = start
            for t in keep:
                at = align(at)
                pos[t] = at
                at += len(data_of(t, failed))
            at = align(at)
            if end - at >= 8:
                free.append([at, end])
        for t in sorted(pending, key=lambda t: -len(data_of(t, failed))):
            b = data_of(t, failed)
            fits = [blk for blk in free if blk[1] - blk[0] >= len(b)]
            if not fits:
                return t, None
            blk = min(fits, key=lambda k: k[1] - k[0])
            pos[t] = blk[0]
            blk[0] = align(blk[0] + len(b))
        return None, pos

    failed = set()
    while True:
        bad, pos = allocate(failed)
        if bad is None:
            break
        problems.append(f'{name}: no space for string at {bad:#x}: {new_text[bad][:50]!r} (left in Japanese)')
        failed.add(bad)
    for t, end in slots.items():
        d[t:end] = b'\0' * (end - t)
    moved = 0
    for t, at in pos.items():
        b = data_of(t, failed)
        d[at:at + len(b)] = b
        if at != t:
            moved += 1
            for l in by_target[t]:
                struct.pack_into('<I', d, l, at - pof0.DATA_BASE)
    return bytes(d), moved, len(slots)


def items_original(items, t):
    for o, _ in items:
        if o['off'] == t:
            return o['jp'].encode('cp932') + b'\0'
    return b'\0'


def build_files(dip_root, elf, edits, problems, report):
    outs = {}
    for f, items in sorted(edits.items()):
        src = elf if f == 'ELF' else os.path.join(os.path.dirname(dip_root), f)
        d = open(src, 'rb').read()
        pool = [(o, b) for o, b in items if o['mode'] == 'pool']
        heur = [(o, b) for o, b in items if o['mode'] != 'pool']
        if pool:
            r = apply_pool(d, pool, problems, f)
            if r is None:
                continue
            d, moved, n = r
            report.append(f'{f}: {n} pointer strings rewritten, {moved} relocated')
        if heur:
            d = apply_heur(d, heur)
        outs[f] = d
    return outs


def write_iso(outs, iso_in, iso_out):
    if os.path.abspath(iso_in) == os.path.abspath(iso_out):
        sys.exit('refusing to overwrite the original ISO')
    print('copying ISO...')
    shutil.copyfile(iso_in, iso_out)
    with open(iso_out, 'r+b') as f:
        dip_off, _ = iso_find(f, '_DATA.DIP')
        idx = dip_index(f, dip_off)
        for name, data in outs.items():
            if name == 'ELF':
                off, size = iso_find(f, 'SLPS_258.27')
                assert len(data) == size
                f.seek(off); f.write(data)
                continue
            fo, fsz = idx[name]
            assert len(data) <= fsz, name
            f.seek(dip_off + fo); f.write(data)
    print('wrote', iso_out)


def main():
    mode, dip_root, elf = sys.argv[1:4]
    problems, report = [], []
    edits = plan(dip_root, elf, problems, report)
    outs = build_files(dip_root, elf, edits, problems, report)
    # graphics edits made by texpatch.py (work/texout mirrors the DIP layout)
    tex_root = os.path.join(WORK, 'texout')
    ntex = 0
    for dp, _, fs in os.walk(tex_root):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), tex_root).replace(os.sep, '/')
            if rel in outs:
                problems.append(f'{rel}: modified by both text and texture patches (texture skipped)')
                continue
            outs[rel] = open(os.path.join(dp, f), 'rb').read(); ntex += 1
    report.append(f'{ntex} texture files replaced')
    report.append(f'{len(outs)} files modified')
    with open(os.path.join(WORK, 'report.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(problems + [''] + report) + '\n')
    print(f'{len(problems)} problems')
    print('\n'.join(report[-6:]))
    if mode == 'build':
        if problems:
            print('note: strings with problems were left in Japanese')
        write_iso(outs, sys.argv[4], sys.argv[5])


if __name__ == '__main__':
    main()
