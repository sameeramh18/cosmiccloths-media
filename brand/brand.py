"""Cosmic Cloths brand kit for videos and posts (1080 x 1920 and 1080 x 1350).

One typeface everywhere: Space Grotesk (any case, weights 400-700).
Kannada script only: Noto Sans Kannada.
Colours: gold #F6CD78 accent, warm white #F8F5EE main, soft #CDCDDC small text.
Logo: the mark, top-right corner, same size and spot on every frame (outro included).
"""
from PIL import Image, ImageFont, ImageFilter
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GF = os.path.join(HERE, '..', 'gfonts', 'gf', 'ofl')
GOLD = (246, 205, 120); WHITE = (248, 245, 238); SOFT = (205, 205, 220)

def font(size, weight=600):
    f = ImageFont.truetype(os.path.join(GF, 'spacegrotesk', 'SpaceGrotesk[wght].ttf'), size)
    f.set_variation_by_axes([max(300, min(700, weight))])
    f._w = weight
    return f

def kannada(size, weight=700):
    f = ImageFont.truetype(os.path.join(GF, 'notosanskannada', 'NotoSansKannada[wdth,wght].ttf'), size)
    f.set_variation_by_axes([max(100, min(900, weight)), 100])
    return f

_MARK = Image.open(os.path.join(HERE, 'cosmiccloths-mark-1024.png')).convert('RGBA')
LOGO_SIZE = 92          # px on a 1080-wide frame
LOGO_MARGIN_X = 52      # from the right edge
LOGO_Y = 196            # below Instagram's top bar
LOGO_OPACITY = 0.9

def logo_layer(W=1080, H=1920, size=LOGO_SIZE, opacity=LOGO_OPACITY, y=LOGO_Y):
    """Full-frame RGBA layer with the mark in the standard top-right spot, soft shadow so it blends on any shot."""
    m = _MARK.resize((size, size), Image.LANCZOS)
    a = m.split()[3].point(lambda v: int(v * opacity)); m.putalpha(a)
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = a.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.6))
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 255)); shadow.putalpha(sh)
    x = W - LOGO_MARGIN_X - size
    L.alpha_composite(shadow, (x, y + 3)); L.alpha_composite(m, (x, y))
    return L
