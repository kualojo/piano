"""Add letter names (C, F#, Bb...) next to every notehead in a vector sheet-music PDF
exported from Sibelius (Opus font). Reads glyph and line positions directly from the PDF.

  letternotes.py in.pdf out.pdf [--stack --fs=8 --offset=0.8] [--preview=N] [--json=notes.json] [--png=DIR]

--preview=N  only the first N systems (lines of music), with a 'preview' footer
--json=FILE  notes with pitch and timing, for playback and the piano roll
--png=DIR    also render each output page as DIR/page-1.png ...
"""
import sys, os, re, json, collections
import pymupdf

SRC, DST = sys.argv[1], sys.argv[2]
DEBUG = '--debug' in sys.argv
STYLE = 'stack' if '--stack' in sys.argv else 'beside'
FS = float(next((a[5:] for a in sys.argv if a.startswith('--fs=')), 5.2))
OFFSET = float(next((a[9:] for a in sys.argv if a.startswith('--offset=')), 1.5))
PAGES = next((a[8:] for a in sys.argv if a.startswith('--pages=')), None)
PREVIEW = int(next((a[10:] for a in sys.argv if a.startswith('--preview=')), 0))
JSON_OUT = next((a[7:] for a in sys.argv if a.startswith('--json=')), None)
PNG_DIR = next((a[6:] for a in sys.argv if a.startswith('--png=')), None)

HEADS = {'œ', '˙', 'w'}            # black, half, whole noteheads (Opus font)
ACCS = {'b': -1, '#': 1, 'n': 0}   # flat, sharp, natural
CLEFS = {'&': 30, '?': 18}         # diatonic number of bottom staff line: E4, G2
LETTERS = 'CDEFGAB'
FLAT_ORDER = 'BEADGCF'
SHARP_ORDER = 'FCGDAEB'
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'DejaVuSans-Bold.ttf')
RESTS = {'Œ': 1, '‰': 0.5, '≈': 0.25, 'Ó': 2, '∑': 0, '-': 0}   # quarter-note beats; 0 = whole bar
FLAGS = {'j': 1, 'J': 1, 'r': 2, 'R': 2}                       # 8th and 16th flags
DIGITS = set('0123456789')
STEP_SEMI = [0, 2, 4, 5, 7, 9, 11]
COLORS = [(0.80, 0.0, 0.0), (0.0, 0.2, 0.85)]  # upper staff red, lower staff blue


def glyphs(page):
    out = []
    for b in page.get_text('rawdict')['blocks']:
        for l in b.get('lines', []):
            for s in l['spans']:
                fn = s['font'].split('+')[-1]
                if not fn.startswith('Opus') or fn.startswith('OpusText'):
                    continue
                for c in s['chars']:
                    ch = c['c']
                    if 0xF000 <= ord(ch) <= 0xF0FF:   # symbol font mapped to private-use codes
                        ch = bytes([ord(ch) - 0xF000]).decode('mac_roman')
                    out.append(dict(c=ch, x=c['origin'][0], y=c['origin'][1],
                                    bbox=pymupdf.Rect(c['bbox']), size=s['size'],
                                    font=s['font']))
    return out


def lines(page):
    hl, vl, ledg, ties, stems = [], [], [], [], []
    beams = []
    for d in page.get_drawings():
        w = d.get('width') or 0
        if d['type'] == 'f' and len(d['items']) == 4 and all(it[0] == 'l' for it in d['items']):
            beams.append(d['rect'])
        for it in d['items']:
            if it[0] == 'c':
                p, q = it[1], it[4]
                if abs(p.y - q.y) < 0.3 and 3 < abs(p.x - q.x) < 120:   # flat curve = tie
                    ties.append((min(p.x, q.x), max(p.x, q.x), p.y))
            if it[0] != 'l':
                continue
            p, q = it[1], it[2]
            if abs(p.y - q.y) < 0.05:
                L = abs(p.x - q.x)
                if L > 60:
                    hl.append((p.y, min(p.x, q.x), max(p.x, q.x)))
                elif 6 < L < 16:
                    ledg.append((p.y, min(p.x, q.x), max(p.x, q.x)))
            elif abs(p.x - q.x) < 0.05 and w > 0.6:
                vl.append((p.x, min(p.y, q.y), max(p.y, q.y)))
            elif abs(p.x - q.x) < 0.05 and abs(p.y - q.y) > 8:
                stems.append((p.x, min(p.y, q.y), max(p.y, q.y)))
    return hl, vl, ledg, ties, stems, beams


def find_staves(hl):
    hl = sorted(hl)
    staves, i = [], 0
    while i + 4 < len(hl):
        g = hl[i:i + 5]
        gaps = [g[k + 1][0] - g[k][0] for k in range(4)]
        if max(gaps) - min(gaps) < 0.3 and 3 < gaps[0] < 12 and abs(g[0][1] - g[4][1]) < 1:
            staves.append(dict(top=g[0][0], bot=g[4][0], sp=sum(gaps) / 4,
                               x0=g[0][1], x1=g[0][2]))
            i += 5
        else:
            i += 1
    return staves


def key_from(accs):
    """accs: list of (alter, diatonic letter idx) in order -> {letter: alter}."""
    if not accs:
        return {}
    alt = accs[0][0]
    order = FLAT_ORDER if alt < 0 else SHARP_ORDER
    n = len(accs)
    got = ''.join(LETTERS[a[1]] for a in accs)
    if got != order[:n]:
        print(f'  warning: unexpected key signature {got}', file=sys.stderr)
    return {L: alt for L in order[:n]}


def name(letter, alter):
    return letter + {-1: 'b', 0: '', 1: '#', -2: 'bb', 2: 'x'}[alter]


def process_page(page, pno, state):
    gl = glyphs(page)
    hl, vl, ledg, ties, stems, beams = lines(page)
    # tight outlines of every printed symbol and word (triplet marks, pedal marks, tempo text...)
    marks, music_marks, tuplets, dots = [], [], [], []
    for b in page.get_text('rawdict', flags=pymupdf.TEXT_ACCURATE_BBOXES)['blocks']:
        for l in b.get('lines', []):
            for sp_ in l['spans']:
                for c in sp_['chars']:
                    if c['c'].strip():
                        marks.append(pymupdf.Rect(c['bbox']))
                        if sp_['font'].split('+')[-1].startswith('Opus'):
                            music_marks.append(marks[-1])
                        fn = sp_['font'].split('+')[-1]
                        ch = c['c']
                        if 0xF000 <= ord(ch) <= 0xF0FF:
                            ch = bytes([ord(ch) - 0xF000]).decode('mac_roman')
                        if fn.startswith('OpusText') and ch == '3':
                            tuplets.append(c['origin'])
                        elif fn.startswith('OpusSpecial') and ch == '™':
                            dots.append(c['origin'])
    staves = find_staves(hl)
    if not staves:
        return [], [], []
    # which staff index within a system (0 = upper / right hand)
    # systems: staves joined by a barline spanning both
    for s in staves:
        s['pos'] = 0
    for a, b in zip(staves, staves[1:]):
        if any(abs(v[1] - a['top']) < 0.6 and abs(v[2] - b['bot']) < 0.6 for v in vl):
            b['pos'] = a['pos'] + 1
    for k, s in enumerate(staves):
        # marks hanging below a staff belong to it, except those just above the next staff (bar numbers, 8va)
        # (judged by the mark's centre: halfway to the next staff, at most 12 spaces)
        s['limit'] = min(s['bot'] + 12 * s['sp'], s['bot'] + 0.5 * (staves[k + 1]['top'] - s['bot']) if k + 1 < len(staves) else 1e9)
    for s in staves:
        s['sys'] = sum(1 for t in staves[:staves.index(s) + 1] if t['pos'] == 0) - 1
        s['bars'] = sorted(v[0] for v in vl if v[1] <= s['top'] + 0.6 and v[2] >= s['bot'] - 0.6)
        # real barlines start and end exactly on staff lines; long stems that cross the staff do not
        tops, bots = [t['top'] for t in staves], [t['bot'] for t in staves]
        s['true_bars'] = sorted(v[0] for v in vl if v[1] <= s['top'] + 0.6 and v[2] >= s['bot'] - 0.6
                                and any(abs(v[1] - t) < 0.4 for t in tops) and any(abs(v[2] - t) < 0.4 for t in bots))
        s['items'] = []
        s['rests'] = []
        s['digits'] = []
        s['notes'] = []

    def staff_base_for(y):
        return min(range(len(staves)), key=lambda i: max(staves[i]['top'] - y, y - staves[i]['bot'], 0))

    def step(s, y):
        return round((s['bot'] - y) / (s['sp'] / 2))

    def needs_ledgers_ok(s, y, x):
        st = step(s, y)
        need = []
        if st <= -2:
            need = [s['bot'] + k * s['sp'] for k in range(1, (-st) // 2 + 1)]
        elif st >= 10:
            need = [s['top'] - k * s['sp'] for k in range(1, (st - 8) // 2 + 1)]
        for ly in need:
            if not any(abs(l[0] - ly) < 0.6 and l[1] - 3 < x < l[2] + 1 for l in ledg):
                return False, len(need)
        return True, len(need)

    def assign(g):
        y, x = g['y'], g['bbox'].x0 + g['bbox'].width / 2
        dist = sorted(range(len(staves)), key=lambda i: max(staves[i]['top'] - y, y - staves[i]['bot'], 0))
        for i in dist[:2]:
            ok, n = needs_ledgers_ok(staves[i], y, x)
            if ok:
                return i
        return dist[0]

    for g in gl:
        if g['c'] in HEADS or g['c'] in ACCS or g['c'] in CLEFS:
            si = assign(g) if g['c'] in HEADS else staff_base_for(g['y'])
            staves[si]['items'].append(g)
        elif g['c'] in RESTS or g['c'] in DIGITS:
            si = staff_base_for(g['y'])
            staves[si]['rests' if g['c'] in RESTS else 'digits'].append(g)
        elif g['c'] in FLAGS:
            state.setdefault('flags', []).append(g)

    total = 0
    out = []
    placed = collections.defaultdict(list)   # label boxes per system, to avoid overlaps
    fs = state['fs']
    for si, s in enumerate(staves):
        items = sorted(s['items'], key=lambda g: g['x'])
        heads = [g for g in items if g['c'] in HEADS]
        clef_base = state['clef'].get(s['pos'], 30)
        key = state['key'].get(s['pos'], {})
        # key signature: run of accidentals right after a clef at the start of the staff
        clefs = [g for g in items if g['c'] in CLEFS]
        first_head_x = heads[0]['x'] if heads else 1e9
        consumed = set()
        if clefs and clefs[0]['x'] < s['x0'] + 30:
            clef_base = CLEFS[clefs[0]['c']]
            run, lastx = [], clefs[0]['bbox'].x1
            for g in items:
                if g['c'] in ACCS and g['c'] != 'n' and g['x'] > clefs[0]['x'] and g['x'] < first_head_x - 2:
                    if g['x'] - lastx < 9 and abs(g['size'] - clefs[0]['size']) < 1:
                        run.append(g); lastx = g['bbox'].x0 + g['bbox'].width
                    else:
                        break
            if run:
                key = key_from([(ACCS[g['c']], (clef_base + step(s, g['y'])) % 7) for g in run])
            else:
                key = {}
            consumed = {id(g) for g in run}
            state['key'][s['pos']] = key
        # mid-staff key-signature changes: run of unattached accidentals right after a barline
        def attached(a):
            return any(0 < h['bbox'].x0 - a['x'] < 32 and abs(h['y'] - a['y']) < 0.8 for h in heads)

        events = []
        for g in items:
            if id(g) in consumed:
                continue
            if g['c'] in CLEFS:
                if g['x'] > s['x0'] + 30:
                    events.append(('clef', g['x'], g))
            elif g['c'] in ACCS:
                if attached(g):
                    events.append(('acc', g['x'], g))
                else:
                    events.append(('loose', g['x'], g))
            else:
                events.append(('head', g['x'], g))
        for bx in s['true_bars']:      # accidentals last until the next real barline
            events.append(('bar', bx, None))
        order = {'bar': 0, 'clef': 1, 'loose': 2, 'acc': 3, 'head': 4}
        events.sort(key=lambda e: (e[1], order[e[0]]))

        measure_acc = {}           # diatonic number -> alter
        last = state['last'].setdefault(s['pos'], {})   # diatonic number -> (alter, right x)
        for d_ in last:
            last[d_] = (last[d_][0], -1e9)   # new system: previous notes are off to the left

        def tied_into(h, prev_x1):
            for t0, t1, ty in ties:
                if h['bbox'].x0 - 8 < t1 < h['bbox'].x0 + 3 and abs(ty - h['y']) < 4.5 and \
                        (abs(t0 - prev_x1) < 8 or (prev_x1 < 0 and t0 < s['x0'] + 80)):
                    return True
            return False
        pending = {}               # step -> (alter, x) waiting for its head
        loose_run = []
        labels = []
        for kind, x, g in events:
            if kind != 'loose' and loose_run:
                lr, loose_run = loose_run, []
                if all(a['c'] == 'n' for a in lr):
                    key = {}
                else:
                    key = key_from([(ACCS[a['c']], (clef_base + step(s, a['y'])) % 7) for a in lr if a['c'] != 'n'])
                state['key'][s['pos']] = key
                if DEBUG:
                    print(f'p{pno+1} staff{si} key change at x={x:.0f}: {key}', file=sys.stderr)
            if kind == 'bar':
                measure_acc = {}
                pending = {}
            elif kind == 'clef':
                clef_base = CLEFS[g['c']]
            elif kind == 'loose':
                loose_run.append(g)
            elif kind == 'acc':
                pending[step(s, g['y'])] = ACCS[g['c']]
            elif kind == 'head':
                st = step(s, g['y'])
                d = clef_base + st
                letter = LETTERS[d % 7]
                if st in pending:
                    measure_acc[d] = pending.pop(st)
                alter = measure_acc.get(d, key.get(letter, 0))
                prev = last.get(d)
                if prev is not None and d not in measure_acc and tied_into(g, prev[1]):
                    alter = prev[0]   # a tie carries the accidental over the barline
                tied = prev is not None and tied_into(g, prev[1])
                last[d] = (alter, g['bbox'].x1)
                s['notes'].append(dict(g=g, midi=12 * (d // 7 + 1) + STEP_SEMI[d % 7] + alter, tied=tied, name=name(letter, alter)))
                labels.append((g, name(letter, alter)))
                if DEBUG:
                    print(f'p{pno+1} staff{si} x={g["x"]:.0f} y={g["y"]:.1f} {g["c"]} {name(letter, alter)}', file=sys.stderr)
                    state['clef'][s['pos']] = clef_base

        # place labels: group heads into chord columns, stack labels to avoid overlap
        cols = []
        for g, txt in sorted(labels, key=lambda t: t[0]['x']):
            if cols and g['x'] - cols[-1][-1][0]['x'] < 7.5 and (g['size'] > 15) == (cols[-1][-1][0]['size'] > 15):
                cols[-1].append((g, txt))
            else:
                cols.append([(g, txt)])
        color = COLORS[min(s['pos'], 1)]
        heads_here = heads

        def lane(s, cx, up):
            # one line per bar for the letters: clear of every note, stem and triplet mark in that bar
            edges = [s['x0']] + s['bars'] + [s['x1'] + 1]
            m0 = max(e for e in edges if e <= cx)
            m1 = min(e for e in edges if e > cx)
            inbar = lambda x: m0 - 1 < x < m1 + 1
            if up:
                ys = [s['top']] + [g['y'] - s['sp'] * 0.6 for g in heads_here if inbar(g['x'])]
                ys += [t[1] for t in stems if inbar(t[0]) and s['top'] - 1 < t[2] < s['bot'] + 4 * s['sp']]
                ys += [r.y0 for r in marks if inbar((r.x0 + r.x1) / 2) and r.y0 > s['top'] - 5 * s['sp'] and r.y0 < s['top'] - 1]
                return min(ys)
            ys = [s['bot']] + [g['y'] + s['sp'] * 0.6 for g in heads_here if inbar(g['x'])]
            ys += [t[2] for t in stems if inbar(t[0]) and s['top'] - 4 * s['sp'] < t[1] < s['bot'] + 1]
            # pedal marks and words below only push the letters they actually sit under
            ys += [r.y1 for r in marks if r.x0 - 6 < cx < r.x1 + 6 and s['bot'] + 1 < r.y1 and (r.y0 + r.y1) / 2 < s['limit']]
            return max(ys)

        for col in cols:
            if STYLE == 'stack':
                # upper staff: letters stacked above the staff/chord; lower staff: below it.
                # sharp = letter in a circle, flat = letter in a square, natural = plain letter
                fnt = state['font']
                up = s['pos'] == 0
                cx = sum(g['bbox'].x0 + g['bbox'].width / 2 for g, _ in col) / len(col)
                ext = lane(s, cx, up)
                by_pitch = sorted(col, key=lambda t: t[0]['y'])   # highest note first
                n = len(col)
                f = fs if col[0][0]['size'] > 15 else fs * 0.75
                step_h = f * 1.22               # room for the circle / square
                half_w = f * 0.62
                pad = s['sp'] * OFFSET
                # push the whole stack further out until it clears labels already placed
                extra = 0
                while True:
                    if up:
                        top = ext - pad - extra - n * step_h
                        box = (cx - half_w, top, cx + half_w, ext - pad - extra)
                    else:
                        top = ext + pad + extra
                        box = (cx - half_w, top, cx + half_w, top + n * step_h)
                    if extra >= step_h * 1.5 or not any(
                            box[0] < o[2] and o[0] < box[2] and box[1] < o[3] and o[1] < box[3] for o in placed[s["sys"]]):
                        break
                    extra += step_h * 0.5
                placed[s["sys"]].append(box)
                for k, (g, txt) in enumerate(by_pitch):   # k=0 (highest note) at the top
                    mid = box[1] + (k + 0.5) * step_h
                    letter, acc = txt[0], txt[1:]
                    shape = 'circle' if acc in ('#', 'x') else 'square' if acc in ('b', 'bb') else None
                    w = fnt.text_length(letter, fontsize=f)
                    out.append(((cx - w / 2, mid + f * 0.36), letter, f, color, shape, (cx, mid), s['sys']))
                    total += 1
                continue
            xs = max(g['bbox'].x1 for g, _ in col) + 0.4
            items_y = sorted(((g['y'], txt, g) for g, txt in col), key=lambda t: t[0])
            # small/cue noteheads: their bbox is narrow already
            gap = fs * 0.82
            ys = [t[0] for t in items_y]
            # relax: push down then pull up so labels keep order with min gap
            for k in range(1, len(ys)):
                ys[k] = max(ys[k], ys[k - 1] + gap)
            shift = (sum(t[0] for t in items_y) - sum(ys)) / len(ys)
            ys = [y + shift for y in ys]
            for (y0, txt, g), y in zip(items_y, ys):
                f = fs if g['size'] > 15 else fs * 0.75   # grace / cue notes get smaller labels
                out.append(((xs, y + f * 0.36), txt, f, color, None, None, s['sys']))
                total += 1
    systems = []
    for st in staves:
        if st['pos'] == 0:
            systems.append([st['top'], st['bot'], st['bot']])
        else:
            systems[-1][1] = st['bot']
    for sy in systems:   # lowest mark (pedal, words) hanging below each system
        lim = next(st['limit'] for st in staves if st['bot'] == sy[1])
        sy[2] = max([sy[1]] + [r.y1 for r in marks if sy[1] + 1 < r.y1 and (r.y0 + r.y1) / 2 < lim])
    flags = state.pop('flags', [])
    rhythm = dict(stems=stems, beams=beams, flags=flags, tuplets=tuplets, dots=dots)
    return out, systems, timing(staves, rhythm, state)


def head_beats(g, r, sp):
    """Written length of one note in quarter-note beats, from its notehead, dots, flags, beams
    and triplet marks, plus its stem direction (+1 up, -1 down, 0 none)."""
    x0, x1, y = g['bbox'].x0, g['bbox'].x1, g['y']
    dotted = any(x1 < dx < x1 + 2.2 * sp and abs(dy - y) < sp * 0.8 for dx, dy in r['dots'])
    mul = 1.5 if dotted else 1
    if g['c'] == 'w':
        return 4 * mul, 0
    st = [t for t in r['stems'] if x0 - 1.2 < t[0] < x1 + 1.2 and t[1] - 3 < y < t[2] + 3]
    if not st:
        return (2 if g['c'] == '˙' else 1) * mul, 0
    t = max(st, key=lambda t: t[2] - t[1])
    up = 1 if abs(t[2] - y) < abs(t[1] - y) else -1
    if g['c'] == '˙':
        return 2 * mul, up
    n = 0
    for f in r['flags']:
        if abs(f['x'] - t[0]) < 2 and t[1] - 12 < f['y'] < t[2] + 12:
            n = max(n, FLAGS[f['c']])
    lv, mine = [], []
    for b in r['beams']:
        if b.x0 - 1 < t[0] < b.x1 + 1 and t[1] - 3 < (b.y0 + b.y1) / 2 < t[2] + 3:
            mine.append(b)
            if not any(abs(b.y0 - o) < 1.5 for o in lv):
                lv.append(b.y0)
    n = max(n, len(lv))
    # a '3' over (or under) this note's beam makes it a triplet
    if any(any(b.x0 - 2 < tx < b.x1 + 2 and b.y0 - 14 < ty < b.y1 + 14 for b in mine) for tx, ty in r['tuplets']):
        mul *= 2 / 3
    return mul / 2 ** n, up


def voice_times(evs, ln):
    """evs: (x, beats, note|None) in one voice of one bar -> [(t, d, note)], scaled to fit the bar."""
    cols = []
    for e in sorted(evs, key=lambda e: e[0]):
        if cols and e[0] - cols[-1][0][0] < 4.5:
            cols[-1].append(e)
        else:
            cols.append([e])
    total = sum(min(e[1] for e in c) for c in cols)
    if not total:
        return []
    # an over-full bar is squeezed to fit; a short one is left as written (hidden rests, pickups)
    scale = ln / total if total > ln or total > 0.85 * ln else 1
    out, t = [], 0
    for c in cols:
        for x, beats, n in c:
            if n is not None:
                out.append((t, min(beats * scale, ln - t), n))
        t += min(e[1] for e in c) * scale
    return out


def timing(staves, r, state):
    """Onset and length of every note, in beats from the start of its system.
    Note lengths come from the notation; each bar is then scaled to fit the time signature,
    which also absorbs triplets and anything misread."""
    notes = []
    sys_bars = {}
    for s in staves:
        pos, sysi = s['pos'], s['sys']
        # time signature: stacked digits at the start of the staff, or after a barline
        dg = sorted(s['digits'], key=lambda g: g['x'])
        tsigs = []
        mid = (s['top'] + s['bot']) / 2
        for g in dg:
            if g['y'] < mid + 0.5 and g['size'] > 15:
                low = [h for h in dg if abs(h['x'] - g['x']) < 4 and h['y'] > g['y'] + s['sp']]
                if low:
                    tsigs.append((g['x'], int(g['c']) * 4 / int(low[0]['c'])))
        edges = [s['x0']] + [b for b in s['true_bars'] if b > s['x0'] + 2] + [s['x1'] + 1]
        edges = sorted(set(round(e, 1) for e in edges))
        bars = []
        for k in range(len(edges) - 1):
            a, b = edges[k], edges[k + 1]
            if b - a < 8:
                continue
            for tx, ln in tsigs:
                if tx < b:
                    state['tsig'][pos] = ln
            bars.append((a, b, state['tsig'].get(pos, 4)))
        if pos == 0:
            sys_bars[sysi] = [ln for _, _, ln in bars]
            if DEBUG:
                print('sys', sysi, 'bars', [(round(a), round(b), ln) for a, b, ln in bars], file=sys.stderr)
        for bi, (a, b, ln) in enumerate(bars):
            evs = []
            for n in s['notes']:
                g = n['g']
                if a <= g['x'] < b and g['size'] > 15:      # grace notes are skipped
                    beats, up = head_beats(g, r, s['sp'])
                    evs.append((g['x'], beats, n, up))
            rests = [(q['x'], RESTS[q['c']] or ln, None, 0) for q in s['rests'] if a <= q['x'] < b and q['size'] > 15]
            # two voices on one staff: stems up and down at the same moment -> time each voice on its own
            ups = [e[0] for e in evs if e[3] > 0]
            two = any(e[3] < 0 and any(abs(e[0] - u) < 4.5 for u in ups) for e in evs)
            if two:
                mid = (s['top'] + s['bot']) / 2
                v1 = [e for e in evs if e[3] >= 0] + [q for q, g in zip(rests, [g for g in s['rests'] if a <= g['x'] < b and g['size'] > 15]) if g['y'] < mid]
                v2 = [e for e in evs if e[3] < 0] + [q for q, g in zip(rests, [g for g in s['rests'] if a <= g['x'] < b and g['size'] > 15]) if g['y'] >= mid]
                timed = voice_times([e[:3] for e in v1], ln) + voice_times([e[:3] for e in v2], ln)
            else:
                timed = voice_times([e[:3] for e in evs + rests], ln)
            for t, d, n in timed:
                notes.append(dict(sys=sysi, bar=bi, t=t, d=d, midi=n['midi'], name=n['name'],
                                  hand='R' if pos == 0 else 'L', tied=n['tied']))
    return notes, sys_bars


def draw_labels(page, out, dy=0.0):
    # white halo / white-filled shape first so letters stay readable over stems, beams and lines
    sh = page.new_shape()
    for pt, txt, f, color, shape, c, _ in out:
        if shape:
            r = f * 0.62
            c = (c[0], c[1] + dy)
            if shape == 'circle':
                sh.draw_circle(c, r)
            else:
                sh.draw_rect(pymupdf.Rect(c[0] - r * 0.92, c[1] - r * 0.92, c[0] + r * 0.92, c[1] + r * 0.92))
            sh.finish(color=color, fill=(1, 1, 1), width=f * 0.11)
        else:
            sh.insert_text((pt[0], pt[1] + dy), txt, fontsize=f, fontname='LBL', fontfile=FONT,
                           color=(1, 1, 1), fill=(1, 1, 1), render_mode=2, border_width=0.25)
    for pt, txt, f, color, shape, c, _ in out:
        sh.insert_text((pt[0], pt[1] + dy), txt, fontsize=f, fontname='LBL', fontfile=FONT, color=color, fill=color)
    sh.commit()


def legend(page):
    """Key in the top margin of page 1."""
    sh = page.new_shape()
    y, x, f = 20, 30, 9
    def word(t, col=(0, 0, 0)):
        nonlocal x
        sh.insert_text((x, y + f * 0.36), t, fontsize=f, fontname='LBL', fontfile=FONT, color=col, fill=col)
        x += pymupdf.Font(fontfile=FONT).text_length(t, fontsize=f)
    def boxed(letter, kind, col):
        nonlocal x
        r = f * 0.62
        c = (x + r, y)
        if kind == 'circle':
            sh.draw_circle(c, r)
        else:
            sh.draw_rect(pymupdf.Rect(c[0] - r * .92, c[1] - r * .92, c[0] + r * .92, c[1] + r * .92))
        sh.finish(color=col, fill=(1, 1, 1), width=f * 0.11)
        w = pymupdf.Font(fontfile=FONT).text_length(letter, fontsize=f)
        sh.insert_text((c[0] - w / 2, y + f * 0.36), letter, fontsize=f, fontname='LBL', fontfile=FONT, color=col, fill=col)
        x += 2 * r + 3
    word('Red', COLORS[0]); word(' = right hand    '); word('Blue', COLORS[1]); word(' = left hand    ')
    boxed('E', 'square', (0, 0, 0)); word('= flat (E flat)    ')
    boxed('F', 'circle', (0, 0, 0)); word('= sharp (F sharp)    plain letter = white key')
    sh.commit()


def label_extent(entries):
    ys = []
    for pt, txt, f, color, shape, c, _ in entries:
        ys += [pt[1] - f * 1.1, pt[1] + f * 0.5]
    return (min(ys), max(ys)) if ys else None


def main():
    doc = pymupdf.open(SRC)
    state = dict(clef={}, key={}, last={}, tsig={}, font=pymupdf.Font(fontfile=FONT), fs=FS)
    timeline, beat0, sys_count = [], 0.0, 0
    m = re.search(r'=\s*(\d{2,3})', doc[0].get_text())
    tempo = int(m.group(1)) if m else 80
    n = 0
    if STYLE != 'stack':
        for pno, page in enumerate(doc):
            page.wrap_contents()
            out, _, _ = process_page(page, pno, state)
            draw_labels(page, out)
            n += len(out)
        doc.save(DST, garbage=3, deflate=True)
        print(f'labelled {n} notes -> {DST}')
        return
    # Stack style needs room above and below every system, so re-flow the systems onto
    # new pages with extra space between them (the music itself is copied unchanged).
    W, H = doc[0].rect.width, doc[0].rect.height
    TOP, BOTTOM, GAP = 34, 24, 6
    new = pymupdf.open()
    page = None
    y = H
    for pno, src in enumerate(doc):
        src.wrap_contents()
        out, systems, (tnotes, sys_bars) = process_page(src, pno, state)
        for i in range(len(systems)):
            starts, acc = [], beat0
            for ln in sys_bars.get(i, [4]):
                starts.append(acc)
                acc += ln
            for tn in tnotes:
                if tn['sys'] == i and tn['bar'] < len(starts):
                    timeline.append(dict(line=sys_count + i, t=round(starts[tn['bar']] + tn['t'], 4),
                                         d=round(tn['d'], 4), midi=tn['midi'], name=tn['name'],
                                         hand=tn['hand'], tied=tn['tied']))
            beat0 = acc
        sys_count += len(systems)
        # drop the original page number; the new pages get their own
        for w in src.get_text('words'):
            if w[4].isdigit() and w[3] < 75 and (w[0] > W - 80 or w[2] < 80) and pno > 0:
                src.add_redact_annot(pymupdf.Rect(w[:4]))
        src.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        n += len(out)
        def split(i):
            # where the band below system i ends: 40% into the gap (8va lines, dynamics and slurs
            # above a system need more room than low notes below one), but past any pedal marks
            bot, low, nxt = systems[i][1], systems[i][2], systems[i + 1][0]
            return min(max(bot + 0.4 * (nxt - bot), low + 1.5), nxt - 12)

        for i, (top, bot, low) in enumerate(systems):
            if PREVIEW and state.setdefault('shown', 0) >= PREVIEW:
                break
            state['shown'] = state.get('shown', 0) + 1
            b0 = split(i - 1) if i else top - 40
            if pno == 0 and i == 0:
                # title, composer and tempo go first on their own, so letters never sit on them
                head = [w[3] for w in src.get_text('words') if top - 60 < w[3] < top - 2]
                b0 = max(head) + 1 if head else top - 22
                page = new.new_page(width=W, height=H)
                page.show_pdf_page(pymupdf.Rect(0, 0, W, b0), doc, pno, clip=pymupdf.Rect(0, 0, W, b0))
                y = b0
            b1 = split(i) if i + 1 < len(systems) else min(max(bot + 40, low + 4), H)
            mine = [e for e in out if e[6] == i]
            ext = label_extent(mine) or (b0, b1)
            v0, v1 = min(b0, ext[0]), max(b1, ext[1])
            h = v1 - v0
            if page is None or y + h > H - BOTTOM:
                page = new.new_page(width=W, height=H)
                y = TOP
            dy = y - v0
            page.show_pdf_page(pymupdf.Rect(0, b0 + dy, W, b1 + dy), doc, pno,
                               clip=pymupdf.Rect(0, b0, W, b1))
            draw_labels(page, mine, dy)
            y += h + GAP
    if PREVIEW:
        while len(new) > 1:
            new.delete_page(-1)
        new[0].insert_text((30, min(y + 24, H - 30)), f'Preview: the first {PREVIEW} lines. Unlock the full piece to see, download and play it all.',
                           fontsize=10, fontname='helv', color=(0.4, 0.4, 0.4))
    else:
        for i, p in enumerate(new):
            p.insert_text((W - 50, H - 12), f'page {i + 1} of {len(new)}', fontsize=8, fontname='helv')
    legend(new[0])
    new.save(DST, garbage=3, deflate=True)
    if PNG_DIR:
        os.makedirs(PNG_DIR, exist_ok=True)
        for i, p in enumerate(new):
            p.get_pixmap(dpi=110).save(os.path.join(PNG_DIR, f'page-{i + 1}.png'))
    if JSON_OUT:
        # ties hold the earlier note on instead of striking again
        merged, held = [], {}
        for e in sorted(timeline, key=lambda e: (e['t'], e['midi'])):
            p = held.get((e['hand'], e['midi']))
            if e['tied'] and p is not None and abs(p['t'] + p['d'] - e['t']) < 0.6:
                p['d'] = round(e['t'] + e['d'] - p['t'], 4)
                continue
            e = {k: v for k, v in e.items() if k != 'tied'}
            merged.append(e)
            held[(e['hand'], e['midi'])] = e
        with open(JSON_OUT, 'w') as fh:
            json.dump(dict(tempo=tempo, lines=sys_count, preview_lines=PREVIEW or None, notes=merged), fh)
    print(f'labelled {n} notes on {len(new)} pages -> {DST}')


main()
