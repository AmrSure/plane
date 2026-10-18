"""
Regenerate raster brand assets (favicons, app icons, logos, spinners, illustrations)
from branding/brand.json and the mark geometry in branding/logo.py.

    python branding/generate_assets.py

Needs Pillow. Each file keeps its original path, format and pixel size, so no code
that imports these assets has to change.
"""

import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logo import BAR_RADIUS, BARS, MARK_RADIUS, MARK_SIZE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "branding" / "brand.json").read_text(encoding="utf-8"))
C = BRAND["colors"]
SS = 4  # supersampling factor for smooth edges

FONT_CANDIDATES = [
    BRAND.get("font", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def hex_rgba(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)) + (a,)


def font(size):
    for f in FONT_CANDIDATES:
        if f and Path(f).is_file():
            return ImageFont.truetype(f, size)
    raise SystemExit("No bold TrueType font found. Set \"font\" in brand.json to a .ttf path.")


def mark(size, color=C["primary"]):
    """The mark on a transparent square canvas of the given size."""
    s = size * SS
    k = s / MARK_SIZE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=MARK_RADIUS * k, fill=hex_rgba(color))
    for x, y, w, h in BARS:
        d.rounded_rectangle([x * k, y * k, (x + w) * k, (y + h) * k], radius=BAR_RADIUS * k, fill=(0, 0, 0, 0))
    return img.resize((size, size), Image.LANCZOS)


def padded_mark(size, pad=0.08, color=C["primary"]):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = max(1, round(size * (1 - 2 * pad)))
    canvas.alpha_composite(mark(inner, color), ((size - inner) // 2, (size - inner) // 2))
    return canvas


def lockup(width, height, text_color):
    """Mark and name side by side, fitted inside width x height."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    m = round(height * 0.86)
    fsize = round(height * 0.62)
    f = font(fsize)
    while True:
        tw = ImageDraw.Draw(canvas).textlength(BRAND["name"], font=f)
        total = m + m * 0.25 + tw
        if total <= width * 0.98 or fsize < 6:
            break
        fsize -= 1
        m = round(m * 0.98)
        f = font(fsize)
    x = round((width - total) / 2)
    canvas.alpha_composite(mark(m), (x, (height - m) // 2))
    d = ImageDraw.Draw(canvas)
    d.text((x + m + m * 0.25, height / 2), BRAND["name"], font=f, fill=hex_rgba(text_color), anchor="lm")
    return canvas


def spinner(size, path):
    frames = []
    w, h = size
    base = round(min(w, h) * 0.42)
    for i in range(48):
        t = i / 48
        scale = 0.9 + 0.1 * (0.5 + 0.5 * math.sin(2 * math.pi * t))
        alpha = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(2 * math.pi * t))
        m = mark(max(1, round(base * scale)))
        m.putalpha(m.getchannel("A").point(lambda a: int(a * alpha)))
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        frame.alpha_composite(m, ((w - m.width) // 2, (h - m.height) // 2))
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=30, loop=0, disposal=2)


def confetti(size, path):
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    palette = [C["primary"], C["accent"], C["light"], "#F59E0B", "#6366F1"]
    for _ in range(26):
        x, y, s = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(4, 10)
        d.rectangle([x, y, x + s, y + s], fill=hex_rgba(rnd.choice(palette)))
    m = mark(round(h * 0.62))
    img.alpha_composite(m, ((w - m.width) // 2, (h - m.height) // 2))
    img.save(path)


def banner(size, path):
    """Wide 'not ready' illustration: mark, a ground line and two cones."""
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ground = round(h * 0.93)
    d.rectangle([0, ground, w, ground + max(4, h // 60)], fill=hex_rgba(C["light"]))
    m = mark(round(h * 0.7))
    img.alpha_composite(m, (round(w * 0.08), ground - m.height))
    for cx, ch in ((0.37, 0.24), (0.42, 0.16)):
        x, ht = round(w * cx), round(h * ch)
        d.polygon([(x - ht * 0.35, ground), (x + ht * 0.35, ground), (x, ground - ht)], fill=hex_rgba(C["accent"]))
    img.save(path, quality=90)


def cards(size, path):
    """Three tilted cards in brand colors, the decorative auth background."""
    w, h = size
    s = SS
    big = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    cw, chh = round(w * 0.46) * s, round(h * 0.6) * s
    for i, col in enumerate([C["dark"], C["primary"], C["accent"]]):
        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        top, bottom = hex_rgba(col, 235), hex_rgba(C["light"], 200)
        for y in range(chh):
            t = y / chh
            cd.line([(0, y), (cw, y)], fill=tuple(round(top[j] * (1 - t) + bottom[j] * t) for j in range(4)))
        mask = Image.new("L", (cw, chh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, chh - 1], radius=cw // 9, fill=255)
        card.putalpha(mask)
        sheared = card.transform(
            (cw, chh + cw // 2), Image.AFFINE, (1, 0, 0, -0.45, 1, 0), resample=Image.BICUBIC
        )
        big.alpha_composite(sheared, (round(i * w * 0.255) * s, 0))
    big.resize((w, h), Image.LANCZOS).save(path, quality=90)


def save_icon(path, size):
    img = padded_mark(size, pad=0.04 if size <= 32 else 0.1)
    if path.suffix == ".ico":
        img.save(path, sizes=[(16, 16), (32, 32), (48, 48)])
    else:
        img.save(path)


def main():
    done = []
    for app in ("web", "admin", "space"):
        fav = ROOT / f"apps/{app}/app/assets/favicon"
        for name, size in (("favicon-16x16.png", 16), ("favicon-32x32.png", 32), ("apple-touch-icon.png", 180), ("favicon.ico", 48)):
            p = fav / name
            if p.exists():
                if p.suffix == ".png":
                    size = Image.open(p).size[0]
                save_icon(p, size)
                done.append(p)
        for p in (ROOT / f"apps/{app}/public/favicon").glob("android-chrome-*.png"):
            save_icon(p, Image.open(p).size[0])
            done.append(p)
        img_dir = ROOT / f"apps/{app}/app/assets/images"
        for variant in ("dark", "light"):
            p = img_dir / f"logo-spinner-{variant}.gif"
            if p.exists():
                spinner(Image.open(p).size, p)
                done.append(p)
        for p in list((ROOT / f"apps/{app}/app/assets").rglob("plane-takeoff.png")):
            confetti(Image.open(p).size, p)
            done.append(p)
        for p in (ROOT / f"apps/{app}/app/assets").rglob("*-horizontal-with-blue-logo.png"):
            text = "#111827" if p.name.startswith("black") else "#FFFFFF"
            w, h = Image.open(p).size
            lockup(w, h, text).save(p)
            done.append(p)

    for p in (ROOT / "apps/web/public/icons").glob("icon-*.png"):
        save_icon(p, Image.open(p).size[0])
        done.append(p)
    pwa = ROOT / "apps/web/public/plane-logos/plane-mobile-pwa.png"
    if pwa.exists():
        save_icon(pwa, Image.open(pwa).size[0])
        done.append(pwa)

    p = ROOT / "apps/space/app/assets/instance/plane-instance-not-ready.webp"
    if p.exists():
        banner(Image.open(p).size, p)
        done.append(p)
    for name in ("gradient-bg-logo.webp", "gradient-logo.webp"):
        p = ROOT / "apps/web/app/assets/auth" / name
        if p.exists():
            cards(Image.open(p).size, p)
            done.append(p)

    logo = ROOT / "apps/api/plane/static/logos/Logo.png"
    if logo.exists():
        w, h = Image.open(logo).size
        lockup(w, h, "#111827").save(logo)
        done.append(logo)

    for p in done:
        print(p.relative_to(ROOT).as_posix())
    print(f"{len(done)} assets regenerated")


if __name__ == "__main__":
    main()
