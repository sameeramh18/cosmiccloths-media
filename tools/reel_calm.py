#!/usr/bin/env python3
"""Calm Reel renderer for Cosmic Cloths.

Builds a 1080x1920 Reel from a JSON spec: background images with ONE slow, smooth camera move
per scene (no shake, no in-out pumping), soft dissolves between scenes, text lines that fade in
one after another, optional graphics (element tile, labels, rings, dotted paths, count-up numbers),
and an FX "punch" (a short, gentle push-in) only where the spec asks for it, e.g. on the reveal.

usage: reel_calm.py spec.json out.mp4
"""
import sys, os, json, math, subprocess
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'brand'))
import brand

W, H, FPS = 1080, 1920, 30
XF = 0.7            # dissolve length (s)
FADE = 0.5          # text fade-in (s)
RISE = 14           # text rise while fading in (px)

def ease(x):  # ease in-out sine, 0..1
    x = max(0.0, min(1.0, x)); return 0.5 - 0.5 * math.cos(math.pi * x)
def ease_out(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

COL = {'white': brand.WHITE, 'gold': brand.GOLD, 'soft': brand.SOFT}

def _greedy(d, words, f, maxw):
    out, cur = [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur: cur = t
        else: out.append(cur); cur = w
    out.append(cur); return out

def wrap(d, text, f, maxw):
    """Balanced wrap: same number of lines as greedy, but lines as even as possible (no lone last word)."""
    words = text.split(); lines = _greedy(d, words, f, maxw)
    if len(lines) == 1: return lines
    lo, hi = maxw * 0.4, maxw
    for _ in range(18):
        mid = (lo + hi) / 2
        if len(_greedy(d, words, f, mid)) > len(lines): lo = mid
        else: hi = mid
    return _greedy(d, words, f, hi)

def text_block(item):
    """Render one text item to an RGBA layer (full frame) once."""
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    style = item.get('style', 'white'); size = item.get('size', 62 if style != 'kicker' else 26)
    weight = item.get('weight', 700 if style in ('white', 'gold') else 600)
    f = brand.font(size, weight); col = COL.get(item.get('color', 'gold' if style == 'gold' else ('soft' if style == 'kicker' else 'white')))
    y = item['y']; maxw = item.get('maxw', 900); lh = int(size * 1.18)
    item['_bottom'] = None
    lines = [item['text']] if style == 'kicker' else wrap(d, item['text'], f, maxw)
    for ln in lines:
        if style == 'kicker':
            sp = 6; tw = sum(d.textlength(c, font=f) + sp for c in ln) - sp; x = (W - tw) / 2
            for c in ln: d.text((x, y), c, font=f, fill=col); x += d.textlength(c, font=f) + sp
        else:
            tw = d.textlength(ln, font=f); d.text(((W - tw) / 2, y), ln, font=f, fill=col)
        y += lh
    item['_bottom'] = y
    # soft shadow for legibility on bright skies
    a = L.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.75))
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 255)); sh.putalpha(a)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0)); out.alpha_composite(sh); out.alpha_composite(L)
    return out

def graphic(item):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L); k = item['kind']
    if k == 'tile':
        x, y, s = item['x'], item['y'], item.get('s', 220)
        d.rounded_rectangle([x - s/2, y - s/2, x + s/2, y + s/2], 18, fill=(14, 12, 20, 215), outline=brand.GOLD + (255,), width=4)
        for txt, fs, dy, col in [(item['top'], 34, -s*0.36, brand.WHITE), (item['mid'], 104, -s*0.2, brand.WHITE), (item['bot'], 30, s*0.24, brand.GOLD)]:
            f = brand.font(fs, 600 if fs < 60 else 700); tw = d.textlength(txt, font=f); d.text((x - tw/2, y + dy), txt, font=f, fill=col)
    elif k == 'label':
        f = brand.font(item.get('size', 28), 600); d.text((item['x'], item['y']), item['text'], font=f, fill=COL[item.get('color', 'white')])
    elif k == 'ring':
        x, y, r = item['x'], item['y'], item['r']; d.ellipse([x-r, y-r, x+r, y+r], outline=brand.GOLD + (230,), width=4)
    elif k == 'path':
        pts = item['pts']
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = int(math.hypot(x1-x0, y1-y0) / 18)
            for i in range(n):
                if i % 2 == 0:
                    a, b = i / n, (i + 0.6) / n
                    d.line([(x0 + (x1-x0)*a, y0 + (y1-y0)*a), (x0 + (x1-x0)*b, y0 + (y1-y0)*b)], fill=brand.GOLD + (230,), width=4)
    return L

class Scene:
    def __init__(s, sp, root):
        s.t0, s.t1 = sp['t0'], sp['t1']
        img = Image.open(os.path.join(root, sp['bg'])).convert('RGB')
        if img.size != (W, H):
            r = max(W / img.width, H / img.height); img = img.resize((math.ceil(img.width*r), math.ceil(img.height*r)), Image.LANCZOS)
            img = img.crop(((img.width-W)//2, (img.height-H)//2, (img.width-W)//2 + W, (img.height-H)//2 + H))
        s.img = img
        s.motion = sp.get('motion', 'push')              # push | pull | drift-left | drift-right | rise | still
        s.amount = sp.get('amount', 0.05)                # total zoom/pan over the scene, kept small
        s.focus = sp.get('focus', [0.5, 0.5])
        s.punch = sp.get('punch')                        # {"at": seconds, "amount": 0.04}
        s.dim = sp.get('dim', 0.0)                       # darken whole frame 0..1
        s.blur = sp.get('blur', 0)
        if s.blur: s.img = s.img.filter(ImageFilter.GaussianBlur(s.blur))
        s.scrim = sp.get('scrim', 'top')                 # top | bottom | both | none
        s.scrim_k = sp.get('scrim_k', 0.62)              # shade strength behind text (raise on bright skies)
        s.items = []
        cursor = None
        for it in sp.get('text', []):
            if it.get('y') is None: it['y'] = (cursor or 330) + it.get('gap', 22)   # stack under the previous line
            s.items.append((it['t'], it.get('out', s.t1), text_block(it))); cursor = it['_bottom']
        for it in sp.get('graphics', []): s.items.append((it['t'], it.get('out', s.t1), graphic(it)))
        s.counters = sp.get('counters', [])
        s.scrim_layer = s.make_scrim()
    def make_scrim(s):
        g = Image.new('L', (1, H))
        for y in range(H):
            top = max(0, 1 - y / 900) ** 1.5 if s.scrim in ('top', 'both') else 0
            bot = max(0, (y - 1000) / 920) ** 1.5 if s.scrim in ('bottom', 'both') else 0
            g.putpixel((0, y), int(255 * min(1, s.scrim_k * max(top, bot) + s.dim)))
        L = Image.new('RGBA', (W, H), (4, 4, 12, 255)); L.putalpha(g.resize((W, H))); return L
    def cam(s, t):
        p = ease((t - s.t0 + XF) / (s.t1 - s.t0 + 2 * XF)); a = s.amount
        z, dx, dy = 1.0 + a, 0.0, 0.0
        if s.motion == 'push': z = 1.0 + a * p
        elif s.motion == 'pull': z = 1.0 + a * (1 - p)
        elif s.motion == 'drift-left': dx = a * (0.5 - p)
        elif s.motion == 'drift-right': dx = a * (p - 0.5)
        elif s.motion == 'rise': dy = a * (0.5 - p)
        elif s.motion == 'still': z = 1.0 + a * 0.2
        if s.punch:
            q = ease_out((t - s.punch['at']) / 0.6) if t >= s.punch['at'] else 0
            z += s.punch.get('amount', 0.04) * q
        return z, dx, dy
    def frame(s, t):
        z, dx, dy = s.cam(t)
        cw, ch = W / z, H / z
        # zoom about the focus point: it stays fixed on screen, so overlays placed on it stay aligned
        x0 = min(max(s.focus[0] * (W - cw) + dx * W, 0), W - cw); y0 = min(max(s.focus[1] * (H - ch) + dy * H, 0), H - ch)
        fr = s.img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch)).convert('RGBA')
        if s.scrim != 'none' or s.dim: fr.alpha_composite(s.scrim_layer)
        for (a, b, layer) in s.items:
            if t < a: continue
            k = ease((t - a) / FADE) * (1 - ease((t - (b - 0.35)) / 0.35) if b < s.t1 else 1)
            if k <= 0: continue
            rise = int(RISE * (1 - ease((t - a) / FADE)))
            lay = layer if k >= 0.999 else Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 0)), layer, k)
            fr.alpha_composite(lay, (0, rise))
        for c in s.counters:
            if t < c['t']: continue
            p = ease_out((t - c['t']) / c.get('dur', 2.0)); v = c['from'] + (c['to'] - c['from']) * p
            txt = c.get('fmt', '{:,.0f}').format(v)
            d = ImageDraw.Draw(fr); f = brand.font(c.get('size', 110), 700); tw = d.textlength(txt, font=f)
            k = ease((t - c['t']) / FADE)
            d.text(((W - tw) / 2, c['y']), txt, font=f, fill=brand.GOLD + (int(255 * k),))
            if c.get('unit'):
                fu = brand.font(30, 500); uw = d.textlength(c['unit'], font=fu)
                d.text(((W - uw) / 2, c['y'] + c.get('size', 110) * 1.12), c['unit'], font=fu, fill=brand.SOFT + (int(255 * k),))
        return fr

def outro_scene(sp, prev_bg, root):
    o = {'t0': sp['t0'], 't1': sp['t1'], 'bg': prev_bg, 'motion': 'still', 'blur': 18, 'dim': 0.45, 'scrim': 'none',
         'text': [{'t': sp['t0'] + 0.2, 'text': 'COSMIC CLOTHS', 'style': 'kicker', 'size': 34, 'color': 'white', 'y': 880},
                  {'t': sp['t0'] + 0.6, 'text': sp.get('line', 'Look up once in a while.'), 'style': 'gold', 'size': 58, 'y': 950, 'maxw': 760},
                  {'t': sp['t0'] + 1.0, 'text': '@cosmiccloths', 'style': 'soft', 'size': 30, 'weight': 500, 'color': 'soft', 'y': 1110}]}
    return Scene(o, root)

def main(spec_path, out):
    spec = json.load(open(spec_path)); root = spec.get('root', os.path.join(HERE, '..', 'fetch', 'out'))
    scenes = []
    for sp in spec['scenes']:
        if sp.get('outro'): scenes.append(outro_scene(sp, scenes[-1] and spec['scenes'][len(scenes)-1]['bg'], root))
        else: scenes.append(Scene(sp, root))
    dur = spec.get('duration', scenes[-1].t1)
    logo = brand.logo_layer(W, H)
    ff = subprocess.Popen(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        cur = [s for s in scenes if s.t0 - XF / 2 <= t < s.t1 + XF / 2]
        if not cur: cur = [scenes[-1]]
        if len(cur) == 1: fr = cur[0].frame(t)
        else:
            a, b = cur[0], cur[1]; k = ease((t - (b.t0 - XF / 2)) / XF)
            fr = Image.blend(a.frame(t), b.frame(t), k)
        fr.alpha_composite(logo)
        if t > dur - 0.6: fr = Image.blend(Image.new('RGBA', (W, H), (0, 0, 0, 255)), fr, max(0, (dur - t) / 0.6))
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close(); ff.wait()
    print('wrote', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
