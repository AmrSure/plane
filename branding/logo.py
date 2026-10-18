"""Shared logo geometry for the brand mark, used by rebrand.py and generate_assets.py.

The mark is a rounded square with three kanban-style bars cut out of it.
Coordinates are in a 48 x 48 box.
"""

MARK_SIZE = 48
MARK_RADIUS = 12
# x, y, width, height of each bar inside the 48 x 48 box
BARS = [(11, 12, 7, 24), (20.5, 12, 7, 15), (30, 12, 7, 20)]
BAR_RADIUS = 3.5


def _rounded_rect(x, y, w, h, r):
    return (
        f"M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}"
        f"V{y + h - r}A{r} {r} 0 0 1 {x + w - r} {y + h}"
        f"H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}"
        f"V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z"
    )


def mark_path():
    """Single path for the mark. Use fill-rule evenodd so the bars are cut out."""
    outer = _rounded_rect(0, 0, MARK_SIZE, MARK_SIZE, MARK_RADIUS)
    bars = "".join(_rounded_rect(x, y, w, h, BAR_RADIUS) for x, y, w, h in BARS)
    return outer + bars


def wordmark_width(name, font_size):
    """Rough rendered width of the name in a bold sans-serif face."""
    return round(len(name) * font_size * 0.62 + font_size * 0.2)
