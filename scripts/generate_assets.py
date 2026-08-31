#!/usr/bin/env python3
"""Generate the landing page images locally.

The design originally pulled its photography from picsum.photos. That service
went down two days before the Release 0 showcase and every image on the home
page broke, so the images are now generated here and served from
shared/assets/. No external host, nothing to fail on venue wifi.

Kept as a script rather than committing unexplained binaries: anyone can see how
the assets were produced and regenerate them if the palette changes.

    python3 scripts/generate_assets.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "shared" / "assets"

# Sampled from the palette in shared/css/theme.css so the images belong to the
# same design rather than sitting beside it.
NAVY_900 = (10, 24, 48)
NAVY_800 = (16, 42, 77)
NAVY_700 = (28, 63, 110)
BLUE_500 = (74, 131, 196)
SKY_300 = (159, 198, 236)

FEATURES = [
    ("feature-01", (NAVY_800, BLUE_500), 0.62),
    ("feature-02", (NAVY_900, NAVY_700), 0.55),
    ("feature-03", (NAVY_700, SKY_300), 0.68),
    ("feature-04", (NAVY_800, SKY_300), 0.58),
    ("feature-05", (NAVY_900, BLUE_500), 0.65),
]


def vertical_gradient(size, top, bottom):
    width, height = size
    base = Image.new("RGB", (1, height))
    pixels = base.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        pixels[0, y] = tuple(
            round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)
        )
    return base.resize(size, Image.BILINEAR)


def ridge(draw, size, horizon, colour, peaks, seed):
    """A mountain-like silhouette, so the image reads as travel rather than a swatch."""
    width, height = size
    points = [(0, height)]
    step = width / peaks
    for i in range(peaks + 1):
        x = i * step
        # Deterministic pseudo-variation: no randomness, so reruns are identical.
        wobble = ((i * seed) % 7) / 7.0
        y = horizon * height - wobble * height * 0.14
        points.append((x, y))
    points.append((width, height))
    draw.polygon(points, fill=colour)


def blend(colour, other, ratio):
    return tuple(round(colour[i] + (other[i] - colour[i]) * ratio) for i in range(3))


def make_feature(name, palette, horizon):
    size = (640, 780)
    top, bottom = palette
    image = vertical_gradient(size, top, bottom)
    draw = ImageDraw.Draw(image, "RGBA")

    # Sun, low opacity, sitting above the horizon.
    cx, cy, r = size[0] * 0.68, size[1] * horizon - 90, 70
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 38))

    ridge(draw, size, horizon + 0.06, blend(bottom, NAVY_900, 0.35) + (235,), 5, 3)
    ridge(draw, size, horizon + 0.16, blend(bottom, NAVY_900, 0.62) + (245,), 4, 5)
    ridge(draw, size, horizon + 0.30, blend(bottom, NAVY_900, 0.82) + (255,), 3, 2)

    image = image.filter(ImageFilter.GaussianBlur(0.6))
    path = ASSETS / f"{name}.jpg"
    image.save(path, "JPEG", quality=86, optimize=True)
    return path


def make_hero():
    size = (1800, 1400)
    image = vertical_gradient(size, NAVY_900, NAVY_700)
    draw = ImageDraw.Draw(image, "RGBA")

    cx, cy, r = size[0] * 0.74, size[1] * 0.30, 190
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 26))

    ridge(draw, size, 0.58, blend(NAVY_700, NAVY_900, 0.30) + (230,), 7, 3)
    ridge(draw, size, 0.70, blend(NAVY_700, NAVY_900, 0.58) + (242,), 5, 5)
    ridge(draw, size, 0.82, blend(NAVY_700, NAVY_900, 0.80) + (255,), 4, 2)

    image = image.filter(ImageFilter.GaussianBlur(1.1))
    path = ASSETS / "hero.jpg"
    image.save(path, "JPEG", quality=84, optimize=True)
    return path


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, palette, horizon in FEATURES:
        path = make_feature(name, palette, horizon)
        print(f"  {path.name}  {path.stat().st_size // 1024} KB")
    path = make_hero()
    print(f"  {path.name}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
