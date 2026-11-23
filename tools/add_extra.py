"""Register second-pass strings (work/extra_candidates.json) in the frozen sheet
as new ids. Noise is dropped; AT spec sheets are auto-translated into
work/en/011.tsv; the rest are listed in work/extra_todo.tsv for translation."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from add_specs_terms import tr_spec
W = os.path.join(os.path.dirname(__file__), '..', 'work')
NOISE = ('[agqx', 'ャャ', 'ケ閾ワ', '戻ｃ潟', 'ャｃャ', 'ABEE', 'ジ$"', '篤Z', '堰{', '÷', 'UDUB', 'ウ属', '熈け', 'Bオブジェクト')
cand = json.load(open(os.path.join(W, 'extra_candidates.json'), encoding='utf-8'))
occ = json.load(open(os.path.join(W, 'strings_frozen.json'), encoding='utf-8'))
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(W, 'sheet_frozen.tsv'), encoding='utf-8')]
by_jp = {r[5].replace('|', '\n'): int(r[0]) for r in rows[1:]}
nid = max(by_jp.values()) + 1
new_rows, auto, todo = [], [], []
for o in cand:
    if any(n in o['jp'] for n in NOISE):
        continue
    occ.append(o)
    t = o['jp']
    if t in by_jp:
        continue
    by_jp[t] = nid
    lines = t.split('\n')
    new_rows.append([str(nid), o['file'], str(len(lines)), str(max(len(x.encode('cp932')) for x in lines)), str(o['room']), t.replace('\n', '|')])
    e = tr_spec(t)
    (auto if e else todo).append((nid, t, e, o['room']))
    nid += 1
with open(os.path.join(W, 'sheet_frozen.tsv'), 'a', encoding='utf-8', newline='\n') as f:
    for r in new_rows: f.write('\t'.join(r) + '\n')
json.dump(occ, open(os.path.join(W, 'strings_frozen.json'), 'w', encoding='utf-8'), ensure_ascii=False)
with open(os.path.join(W, 'en', '013.tsv'), 'w', encoding='utf-8', newline='\n') as f:
    for i, t, e, _ in auto: f.write(f"{i}\t{t.replace(chr(10), '|')[:2]}\t{e}\n")
with open(os.path.join(W, 'extra_todo2.tsv'), 'w', encoding='utf-8', newline='\n') as f:
    for i, t, _, room in todo: f.write(f"{i}\t{room}\t{t.replace(chr(10), '|')}\n")
print(len(new_rows), 'new ids:', len(auto), 'auto,', len(todo), 'to translate')
