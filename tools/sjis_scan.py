"""Scan files for runs of Shift-JIS Japanese text. Usage: sjis_scan.py <dir_or_file> [minchars] [show]"""
import os, sys, re, collections
sys.stdout.reconfigure(encoding="utf-8")

# double-byte SJIS (kana/kanji/fullwidth punctuation) runs
PAT = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]|[\x20-\x7e]){4,}')

def runs(data, minc):
    out = []
    for m in PAT.finditer(data):
        b = m.group()
        try:
            s = b.decode('cp932')
        except UnicodeDecodeError:
            continue
        jp = sum(1 for c in s if '぀' <= c <= 'ヿ' or '一' <= c <= '鿿')
        kana = sum(1 for c in s if '぀' <= c <= 'ゟ')
        if jp >= minc and kana >= 2 and jp >= 0.6 * len(s.replace(' ', '')):
            out.append((m.start(), s))
    return out

root = sys.argv[1]; minc = int(sys.argv[2]) if len(sys.argv) > 2 else 3
show = int(sys.argv[3]) if len(sys.argv) > 3 else 0
paths = [root] if os.path.isfile(root) else [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
byext = collections.Counter(); cnt = collections.Counter()
for p in sorted(paths):
    data = open(p, 'rb').read()
    r = runs(data, minc)
    if r:
        cnt[p] = len(r); byext[os.path.splitext(p)[1]] += len(r)
        if show:
            print(f'== {os.path.relpath(p, root) if p != root else p}  ({len(r)} strings)')
            for off, s in r[:show]:
                print(f'  {off:08x}: {s[:80]}')
print('strings by extension:', dict(byext.most_common()))
print('files with text:', len(cnt))
