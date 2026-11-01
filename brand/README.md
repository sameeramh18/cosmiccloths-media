# Cosmic Cloths brand kit

- **Typeface:** Space Grotesk for everything (any case, weights 400-700). Kannada script only: Noto Sans Kannada. Both from github.com/google/fonts (`ofl/spacegrotesk`, `ofl/notosanskannada`).
- **Colours:** gold `#F6CD78` (accent), warm white `#F8F5EE` (main), soft `#CDCDDC` (small text).
- **Logo:** `cosmiccloths-mark-1024.png` (warm-white rings, gold star and moon, transparent). Dark version for light backgrounds: `cosmiccloths-mark-dark-1024.png`.
- **Logo placement (every video, post, cover, Story):** top-right, 92 px wide on a 1080-wide frame, 52 px from the right edge, top at y 196, 90% opacity, soft shadow. Same spot on every frame including the outro. Never a big logo in the middle.
- `brand.py` gives `font()`, `kannada()` and `logo_layer()`; fonts expected at `../gfonts/gf/ofl/` (adjust the path).
