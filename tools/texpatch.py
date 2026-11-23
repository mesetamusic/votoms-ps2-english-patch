"""Replace Japanese label art in menu textures with rendered English text.

Each label is defined once on a reference texture (file, entry, rect). Its
opaque-pixel mask is then searched for in every texture with the same entry
name, so all copies/variants get the same edit. Text is rendered with Windows
fonts (render_text.ps1), fitted into the label box, and quantized to the
texture's existing palette (the game tints these grayscale sheets itself).

usage: texpatch.py <dip_root> <out_root>   (writes patched files under out_root)
"""
import sys, os, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import tex

HERE = os.path.dirname(os.path.abspath(__file__))
SS = 4  # supersampling for rendering

# (ref file, entry, rect, english, options)
LABELS = [
    # longer variants first, so their tail isn't matched by the shorter label
    ('menu/ScenarioSelect.tex', 'Location', (3, 81, 143, 22), 'Mission Completion', dict(italic=True)),
    ('menu/ScenarioSelect.tex', 'Main', (1, 1, 149, 29), 'Mission Completion', dict(italic=True)),
    ('menu/MissionSelect.tex', 'Location', (315, 1, 68, 23), 'Completion', dict(italic=True, squeeze=0.5)),
    ('menu/MissionSelect.tex', 'Location', (1, 58, 105, 22), 'Required:', dict(italic=True)),
    ('menu/MissionSelect.tex', 'Location', (150, 56, 87, 24), 'Best Rank:', dict(italic=True)),
    ('menu/MissionSelect.tex', 'Location', (88, 81, 58, 20), 'Completion', dict(italic=True)),
    ('menu/MissionSelect.tex', 'Main', (1, 1, 145, 29), 'Mission Completion', dict(italic=True)),
    ('menu/MissionSelect.tex', 'Main', (134, 196, 118, 17), 'Scenario Select', dict(outline=0)),
    ('menu/MissionStart.tex', 'MissionStart', (4, 6, 183, 53), 'Objective', dict()),
    ('menu/MissionStart.tex', 'MissionStart', (198, 6, 169, 53), 'Failure', dict()),
]


MISSION_TITLES = ['Tutorial', 'Battling', 'The Deal', 'Red Shoulder', 'Bonds', 'Assemble EX-10', 'Upstream',
    'Blackout', 'Showdown', 'Vendetta', 'Perfect Soldier', 'Carnage', 'Meteor', 'Blow Battle', 'Real Battle',
    'Trap', 'Diversion', 'Return', 'Assault', 'Recon', 'Counterattack', 'Summit', 'Escape', 'Berserga Story',
    'Seizure', 'Return Fire', 'Suspicion', 'Flashpoint', 'Entangled', 'Crossing', 'Sweep', 'Supplies',
    'Breakout', 'River Crossing', 'Tragedy', 'Target', 'Unity', 'Deadline', 'Last Stand', 'Lone Shadow',
    'Fierce Battle', 'Desert', 'Crush the Allies', 'Lifeline', 'Demon', 'Roots of Ambition',
    'The Last Red Shoulder', 'Big Battle', 'Shining Heresy', 'Fyana']
SCEN_A = [('SCENARIO 1', 'Woodo'), ('SCENARIO 2', 'Kummen'), ('SCENARIO 3', 'Sansa'), ('SCENARIO 4', 'Quent'),
          ('SCENARIO EX', 'Roots of Ambition'), ('SCENARIO EX', 'The Last Red Shoulder'), ('SCENARIO EX', 'Big Battle'),
          ('SCENARIO EX', 'Shining Heresy'), ('SCENARIO EX', 'The Pailsen Files'), ('SCENARIO EX', 'Berserga Story')]
SCEN_B = ['Woodo', 'Kummen', 'Sansa', 'Quent', 'Roots of Darkness', 'The Last Red Shoulder', 'Big Battle',
          'Shining Heresy', 'Berserga Story', 'New OVA']
# whole title cards: (file, entry, new top line or None to keep it, title, outline)
CARDS = ([('menu/missiontitle%02d.txc' % i, '', None, t, 0) for i, t in enumerate(MISSION_TITLES)]
         + [('menu/ScenarioName.tex', 'ScenarioName%02d' % (i + 1), h, t, None) for i, (h, t) in enumerate(SCEN_A)]
         + [('menu/ScenarioNames.tex', 'ScenarioName%02d' % (i + 1), None, t, None) for i, t in enumerate(SCEN_B)])


def render(text, height, italic=False, bold=True, outline=None, font='Arial'):
    """Render white text (black outline) at SS x the requested height -> (w, h, rgba)."""
    hh = height * SS
    ol = max(1, hh // 9) if outline is None else outline * SS
    fd, path = tempfile.mkstemp(suffix='.png'); os.close(fd)
    args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            os.path.join(HERE, 'render_text.ps1'), '-Text', text, '-Height', str(int(hh * 0.8)),
            '-Out', path, '-Font', font, '-Outline', str(ol)]
    if bold: args.append('-Bold')
    if italic: args.append('-Italic')
    subprocess.run(args, check=True, capture_output=True)
    img = tex.read_png(path); os.remove(path)
    return img


def fit(img, bw, bh, min_squeeze=0.6):
    """Area-resample img into at most bw x bh, squeezing width before shrinking."""
    w, h, px = img
    sy = bh / h
    sx = sy
    if w * sx > bw:
        sx = bw / w
        if sx < sy * min_squeeze:
            sy = sx / min_squeeze
    ow, oh = max(1, round(w * sx)), max(1, round(h * sy))
    out = bytearray(ow * oh * 4)
    for oy in range(oh):
        ya, yb = oy / sy, min(h, (oy + 1) / sy)
        for ox in range(ow):
            xa, xb = ox / sx, min(w, (ox + 1) / sx)
            g_acc = a_acc = tot = 0.0
            for y in range(int(ya), min(h, int(yb + 0.999))):
                wy = min(yb, y + 1) - max(ya, y)
                if wy <= 0: continue
                for x in range(int(xa), min(w, int(xb + 0.999))):
                    wx = min(xb, x + 1) - max(xa, x)
                    if wx <= 0: continue
                    k = (y * w + x) * 4; a = px[k + 3] / 255 * wx * wy
                    g_acc += px[k] * a; a_acc += a; tot += wx * wy
            j = (oy * ow + ox) * 4
            al = a_acc / tot if tot else 0
            g = g_acc / a_acc if a_acc else 0
            out[j:j + 4] = bytes((int(g), int(g), int(g), int(al * 255)))
    return ow, oh, out


def nearest(pal, g, a):
    best, bi = None, 0
    for i, (r, gg, b, pa) in enumerate(pal):
        pa2 = min(255, pa * 2)
        dist = (((r - g) ** 2 + (gg - g) ** 2 + (b - g) ** 2) / 3 * (a / 255) ** 2) + ((pa2 - a) * 1.5) ** 2
        if best is None or dist < best: best, bi = dist, i
    return bi


def opaque_rows(t, thresh=8):
    W, H = t['w'], t['h']
    on = bytes(1 if t['pal'][c][3] > thresh else 0 for c in range(len(t['pal'])))
    tr = bytes.maketrans(bytes(range(len(on))), on) if len(on) == 256 else None
    idx = bytes(t['idx'])
    if tr is None:
        tr = bytes.maketrans(bytes(range(16)) + bytes(range(16, 256)), on + bytes(240))
    m = idx.translate(tr)
    return [m[y * W:(y + 1) * W] for y in range(H)]


def find(t, rows, full):
    """Positions where the mask rows occur (allowing ~3% mismatched pixels)."""
    W, H = t['w'], t['h']; h, w = len(rows), len(rows[0])
    r0 = max(range(h), key=lambda i: sum(rows[i]))
    hits = []
    for y in range(r0, H - (h - r0) + 1):
        s = 0
        while True:
            x = full[y].find(rows[r0], s)
            if x < 0: break
            s = x + 1
            if x + w > W: continue
            yy = y - r0; bad = 0; lim = w * h * 0.03
            for i in range(h):
                a, b = full[yy + i][x:x + w], rows[i]
                bad += sum(p != q for p, q in zip(a, b))
                if bad > lim: break
            if bad <= lim: hits.append((x, yy))
    return hits


def paint(t, rect, art):
    x0, y0, bw, bh = rect; W = t['w']
    clear = min(range(len(t['pal'])), key=lambda i: t['pal'][i][3])
    for y in range(bh):
        for x in range(bw):
            t['idx'][(y0 + y) * W + x0 + x] = clear
    aw, ah, px = art
    ox, oy = x0 + (bw - aw) // 2, y0 + (bh - ah) // 2
    cache = {}
    for y in range(ah):
        for x in range(aw):
            k = (y * aw + x) * 4; g, a = px[k], px[k + 3]
            if a < 16: continue
            key = (g >> 2, a >> 2)
            if key not in cache: cache[key] = nearest(t['pal'], g, a)
            t['idx'][(oy + y) * W + ox + x] = cache[key]


def sample_colors(t, rect):
    """(fill, stroke) RGB used by the original art inside rect."""
    x0, y0, bw, bh = rect; W = t['w']; cnt = {}
    for y in range(y0, y0 + bh):
        for x in range(x0, x0 + bw):
            c = t['idx'][y * W + x]
            if t['pal'][c][3] >= 100: cnt[c] = cnt.get(c, 0) + 1
    if not cnt: return (255, 255, 255), (0, 0, 0)
    lum = lambda c: sum(t['pal'][c][:3])
    top = max(lum(c) for c in cnt); bot = min(lum(c) for c in cnt)
    fill = max((c for c in cnt if lum(c) >= top * 0.7), key=lambda c: cnt[c])
    stroke = max((c for c in cnt if lum(c) <= bot + 60), key=lambda c: cnt[c])
    return t['pal'][fill][:3], t['pal'][stroke][:3]


def nearest_rgb(pal, rgb, a):
    best, bi = None, 0
    for i, (r, g, b, pa) in enumerate(pal):
        pa2 = min(255, pa * 2)
        dist = ((r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2) / 3 * (a / 255) ** 2 + ((pa2 - a) * 1.5) ** 2
        if best is None or dist < best: best, bi = dist, i
    return bi


def paint_color(t, box, art, colors, bottom=False):
    """Draw art (white fill / black outline) recoloured to colors=(fill, stroke), no clearing."""
    x0, y0, bw, bh = box; W = t['w']; fill, stroke = colors
    aw, ah, px = art
    ox = x0 + (bw - aw) // 2
    oy = y0 + (bh - ah) if bottom else y0 + (bh - ah) // 2
    cache = {}
    for y in range(ah):
        for x in range(aw):
            k = (y * aw + x) * 4; g, a = px[k], px[k + 3]
            if a < 16: continue
            key = (g >> 2, a >> 2)
            if key not in cache:
                f = g / 255
                rgb = tuple(int(stroke[i] + (fill[i] - stroke[i]) * f) for i in range(3))
                cache[key] = nearest_rgb(t['pal'], rgb, a)
            t['idx'][(oy + y) * W + ox + x] = cache[key]


def union(lst):
    x0 = min(b[0] for b in lst); y0 = min(b[1] for b in lst)
    return (x0, y0, max(b[0] + b[2] for b in lst) - x0, max(b[1] + b[3] for b in lst) - y0)


def desc_h(text, h, tex_h):
    """Box height: letters with descenders hang below the baseline instead of shrinking the word."""
    return int(h * 1.22) if tex_h > 64 and any(c in 'gjpqy' for c in text) else h


def do_cards(files, decoded, all_tex):
    report = []
    by_mask = {}
    for k in all_tex:
        if k not in decoded:
            try: decoded[k] = tex.decode(files[k[0]], k[1])
            except Exception: continue
        by_mask.setdefault(b''.join(opaque_rows(decoded[k])), []).append(k)
    for ref, entry, head_text, title, outline in CARDS:
        rel = 'root/' + ref; d = files[rel]
        off = 0 if not entry else next(o for n, o, s in tex.entries(d) if n == entry)
        rt = decoded[(rel, off)]
        targets = by_mask[b''.join(opaque_rows(rt))]
        W, H = rt['w'], rt['h']
        bs = [b for b in tex.blobs(rt) if b[2] * b[3] > 12]
        heads = [b for b in bs if b[1] + b[3] <= 21] if H <= 64 else []
        body = union([b for b in bs if b not in heads])
        main_h = max(b[3] for b in bs if b not in heads)
        if H > 64:  # mission title cards: one consistent size, kept inside the texture
            two = body[3] > 1.6 * main_h
            main_h = 64
            if not two and body[3] < main_h:
                mid = body[1] + body[3] // 2
                body = (body[0], mid - 32, body[2], 64)
        plan = []
        if head_text and heads:
            hd = union(heads); cx = hd[0] + hd[2] // 2; bw = max(hd[2], 130)
            box = (cx - bw // 2, hd[1], bw, hd[3])
            art = fit(render(head_text, hd[3], outline=1), box[2], box[3])
            plan.append((box, art, sample_colors(rt, hd), False))
        bw = min(W - 8, max(body[2], int(W * 0.85)))
        cx = body[0] + body[2] // 2
        x0 = min(max(4, cx - bw // 2), W - 4 - bw)
        cols = sample_colors(rt, body)
        words = title.split(' ')
        if body[3] > 1.6 * main_h and len(words) > 1:
            # two-line original: split at the space nearest the middle
            cut = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
            for txt, y in ((' '.join(words[:cut]), body[1]), (' '.join(words[cut:]), body[1] + body[3] - main_h)):
                hh = desc_h(txt, main_h, H)
                box = (x0, y, bw, hh)
                plan.append((box, fit(render(txt, hh, italic=True, outline=outline), bw, hh, 0.7), cols, True))
        else:
            y = body[1] + body[3] - main_h if body[3] <= 1.6 * main_h else body[1] + (body[3] - main_h) // 2
            hh = desc_h(title, main_h, H)
            box = (x0, y, bw, hh)
            art = fit(render(title, hh, italic=True, outline=outline), box[2], box[3], 0.7)
            plan.append((box, art, cols, True))
        clear_from = 0 if (head_text or not heads) else union(heads)[1] + union(heads)[3] + 1
        for k in targets:
            t = decoded[k]
            clear = min(range(len(t['pal'])), key=lambda i: t['pal'][i][3])
            for i in range(clear_from * t['w'], t['w'] * t['h']): t['idx'][i] = clear
            for box, art, cols, bottom in plan:
                paint_color(t, box, art, cols, bottom)
        report.append(f'card {title!r:24} {len(targets)} copies')
    return report


def encode(d, t):
    d = bytearray(d); o = t['data']
    if t['bpp'] == 4:
        for i in range(t['n']):
            d[o + i] = t['idx'][2 * i] | (t['idx'][2 * i + 1] << 4)
    else:
        d[o:o + t['n']] = t['idx']
    return bytes(d)


def main(root, out):
    base = os.path.dirname(root)
    files = {}
    for dp, _, fs in os.walk(os.path.join(root, 'menu')):
        for f in fs:
            if f.lower().endswith(('.tex', '.txc')):
                rel = os.path.relpath(os.path.join(dp, f), base).replace(os.sep, '/')
                files[rel] = open(os.path.join(dp, f), 'rb').read()

    def textures(name):
        for rel, d in files.items():
            if d[:4] in (b'RTX3', b'TIM2'): continue
            try: ents = tex.entries(d)
            except Exception: continue
            for n, off, size in ents:
                if n == name and off + 4 <= len(d) and d[off:off + 4] == b'RTX3':
                    yield rel, off

    decoded, masks, arts, report = {}, {}, {}, []
    for ref, name, rect, text, opt in LABELS:
        d = files['root/' + ref]
        off = next(o for n, o, s in tex.entries(d) if n == name)
        rt = tex.decode(d, off)
        rows = [r[rect[0]:rect[0] + rect[2]] for r in opaque_rows(rt)[rect[1]:rect[1] + rect[3]]]
        key = (text, rect[2], rect[3], tuple(sorted(opt.items())))
        if key not in arts:
            ro = {k: v for k, v in opt.items() if k != 'squeeze'}
            arts[key] = fit(render(text, rect[3], **ro), rect[2], rect[3], opt.get('squeeze', 0.6))
        hits = 0
        for rel, off in textures(name):
            k = (rel, off)
            if k not in decoded:
                decoded[k] = tex.decode(files[rel], off)
                masks[k] = opaque_rows(decoded[k])
            t = decoded[k]
            found = find(t, rows, masks[k])
            for (x, y) in found:
                paint(t, (x, y, rect[2], rect[3]), arts[key]); hits += 1
            if found:
                masks[k] = opaque_rows(t)
        report.append(f'{text!r:22} {name:14} {hits} placements')
    all_tex = []
    for rel, d in files.items():
        if d[:4] in (b'RTX3', b'TIM2'):
            all_tex.append((rel, 0)); continue
        try: ents = tex.entries(d)
        except Exception: continue
        for n, off, size in ents:
            if off + 4 <= len(d) and d[off:off + 4] in (b'RTX3', b'TIM2'):
                try: tex.header(d, off)
                except Exception: continue
                all_tex.append((rel, off))
    report += do_cards(files, decoded, all_tex)
    for (rel, off), t in decoded.items():
        files[rel] = encode(files[rel], t)
    written = []
    for rel, d in files.items():
        if d != open(os.path.join(base, rel), 'rb').read():
            p = os.path.join(out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(d); written.append(rel)
    print('\n'.join(report))
    print(len(written), 'files written:', ', '.join(written))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
