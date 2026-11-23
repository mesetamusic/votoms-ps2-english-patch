"""Append text.mtt pointer strings the extractor missed (AT spec sheets, model
names) to the frozen sheet as new ids, and write work/en/010.tsv for them."""
import sys, struct, re, json, os
sys.path.insert(0, os.path.dirname(__file__))
import pof0
root = sys.argv[1]
W = os.path.join(os.path.dirname(__file__), '..', 'work')
F = 'root/menu/text.mtt'
occ = json.load(open(os.path.join(W, 'strings_frozen.json'), encoding='utf-8'))
rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(W, 'sheet_frozen.tsv'), encoding='utf-8')]
by_jp = {r[5].replace('|', '\n'): int(r[0]) for r in rows[1:]}
next_id = max(int(r[0]) for r in rows[1:]) + 1
have = {(o['file'], o['off']) for o in occ}
d = open(os.path.join(os.path.dirname(root), F), 'rb').read()
found = {}
for l in pof0.pointer_locations(d):
    t = struct.unpack_from('<I', d, l)[0] + pof0.DATA_BASE
    if (F, t) in have: continue
    s = d[t:d.index(b'\0', t)]
    try: txt = s.decode('cp932')
    except UnicodeDecodeError: continue
    if re.search('[぀-ヿ一-鿿]', txt) and len(s) > 3:
        found[t] = (s, txt)
NAMES = [('ベルゼルガBTS　“ブルーナイト”', 'Berserga BTS "Blue Knight"'),
         ('スコープドッグ', 'Scopedog'), ('マーシィドッグ', 'Mercydog'), ('パープルベア', 'Purple Bear'),
         ('ストロングバックス', 'Strong Bacchus'), ('ファッティー', 'Fatty'), ('エクルビス', 'Ecrevisse'),
         ('ツヴァーク', 'Zwerg'), ('ラビドリードッグ', 'Rabidlydog'), ('ブラッドサッカー', 'Bloodsucker'),
         ('エルドスピーネ', 'Erdspinne'), ('オーデルバックラー', 'Oder Buckler'), ('ストライクドッグ', 'Strikedog')]
TERMS = [('基本待機重量', 'Weight'), ('巡航走行速度', 'Cruise Speed'), ('標準交換時間', 'PR Swap'),
         ('PR液総量', 'PR Volume'), ('PR液', 'PR Fluid'), ('全高', 'Height'), ('装甲厚', 'Armor'),
         ('固定武装', 'Fixed Arms'), ('11ミリ3連装機関銃', '11mm Triple MG'), ('11ミリ機関銃', '11mm MG'),
         ('スモークディスチャージャー', 'Smoke Discharger'), ('アームパンチ', 'Arm Punch'),
         ('パイルバンカー', 'Pile Bunker'), ('なし', 'None'), ('リットル', 'L'),
         ('：', ':'), ('～', '-'), ('－', '-'), ('・', '-'), ('Ⅱ', 'II'), ('×', 'x'), ('　', ' ')]
def tr(txt):
    if txt == '%d体': return '%d'
    for a, b in NAMES + TERMS: txt = txt.replace(a, b)
    assert all(ord(c) < 128 for c in txt), txt
    return txt.replace('\n', '|')
new_rows, en = [], {}
for t, (s, txt) in sorted(found.items()):
    occ.append(dict(file=F, off=t, len=len(s), room=len(s), mode='pool', jp=txt))
    if txt in by_jp: continue
    by_jp[txt] = next_id
    lines = txt.split('\n')
    new_rows.append([str(next_id), F, str(len(lines)), str(max(len(x.encode('cp932')) for x in lines)), '-1', txt.replace('\n', '|')])
    en[next_id] = (txt, tr(txt))
    next_id += 1
with open(os.path.join(W, 'sheet_frozen.tsv'), 'a', encoding='utf-8', newline='\n') as f:
    for r in new_rows: f.write('\t'.join(r) + '\n')
json.dump(occ, open(os.path.join(W, 'strings_frozen.json'), 'w', encoding='utf-8'), ensure_ascii=False)
with open(os.path.join(W, 'en', '010.tsv'), 'w', encoding='utf-8', newline='\n') as f:
    for i, (jp, e) in en.items():
        f.write(f"{i}\t{jp.replace(chr(10), '|')[:2]}\t{e}\n")
print('added', len(found), 'occurrences,', len(new_rows), 'new ids')
