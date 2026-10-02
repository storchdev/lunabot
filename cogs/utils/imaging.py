from functools import cache
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw

__all__ = ("RANK_CARDS", "generate_rank_card")

# All rank card templates share the same geometry (1280x470).
# Measured from assets/rankcards/standard/template.png.
AV_BOX = (130, 36, 494, 400)  # avatar fills out to the lavender ring's outer edge
BAR_BOX = (502, 399, 1222, 435)  # inset ~16px inside the trough (x 484-1241, y 386-452)
BAR_RADIUS = 18
BAR_ALPHA = 255
DIGIT_CENTER_X = 678  # level number is centered on this x
DIGIT_TOP = 180  # digits were cropped at y=225 in the originals; drawn 45px higher
DIGIT_KERNING = -8
MASK_SUPERSAMPLE = 4  # masks are drawn this many times larger, then downsampled

# card name -> (left, right) progress bar gradient colors
RANK_CARDS = {
    "standard": ("#e48ccb", "#9a82e6"),
    "blue": ("#7c99de", "#5e68bf"),
    "purple": ("#a88ae8", "#7757d6"),
    "pink": ("#ff6fbf", "#e0439f"),
    "winter": ("#6fb4ff", "#4a63e8"),
    "spring": ("#ff6f96", "#e0406f"),
    "summer": ("#ffb23f", "#ff6a1f"),
    "fall": ("#ff8a3d", "#c43d1a"),
    "halloween": ("#ff9a1f", "#8a3de0"),
    "christmas": ("#4fd07a", "#1f9a4f"),
}


@cache
def _template(card: str) -> Image.Image:
    return Image.open(f"assets/rankcards/{card}/template.png").convert("RGBA")


@cache
def _digit(card: str, digit: str) -> Image.Image:
    return Image.open(f"assets/rankcards/{card}/digits/{digit}.png").convert("RGBA")


@cache
def _badge(badge_set: str, slot: int) -> Image.Image:
    return Image.open(f"assets/badges/{badge_set}/{slot}.png").convert("RGBA")


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


@cache
def _bar_gradient(card: str) -> Image.Image:
    left, right = (_hex_to_rgb(c) for c in RANK_CARDS[card])
    w = BAR_BOX[2] - BAR_BOX[0]
    h = BAR_BOX[3] - BAR_BOX[1]
    grad = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(grad)
    for x in range(w):
        t = x / (w - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(left, right))
        draw.line([(x, 0), (x, h)], fill=(*color, BAR_ALPHA))
    return grad


def _aa_mask(size: tuple[int, int], shape: str, **kwargs) -> Image.Image:
    """An antialiased L-mode mask of `shape` ("ellipse" or "rounded_rectangle")."""
    ss = MASK_SUPERSAMPLE
    big = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    box = [(0, 0), (big.width - 1, big.height - 1)]
    kwargs = {k: v * ss for k, v in kwargs.items()}
    getattr(ImageDraw.Draw(big), shape)(box, fill=255, **kwargs)
    return big.resize(size, Image.LANCZOS)


def generate_rank_card(
    card: str,
    level: int,
    av_file,
    percent: float,
    badges: list[tuple[str, int]] = (),
) -> BytesIO:
    """Render a rank card.

    `badges` is a list of (badge_set, slot) pairs; each badge overlay already
    sits at its slot's position on the card, so it is composited as-is.
    """
    im = _template(card).copy()

    av_size = (AV_BOX[2] - AV_BOX[0], AV_BOX[3] - AV_BOX[1])
    with Image.open(av_file) as av:
        av = av.convert("RGBA").resize(av_size, Image.LANCZOS)
    mask = _aa_mask(av_size, "ellipse")
    av.putalpha(ImageChops.multiply(av.getchannel("A"), mask))
    im.alpha_composite(av, AV_BOX[:2])

    fill_w = round((BAR_BOX[2] - BAR_BOX[0]) * max(0.0, min(1.0, percent)))
    if fill_w > 0:
        bar = _bar_gradient(card).crop((0, 0, fill_w, BAR_BOX[3] - BAR_BOX[1]))
        radius = min(BAR_RADIUS, fill_w // 2)
        mask = _aa_mask(bar.size, "rounded_rectangle", radius=radius)
        bar.putalpha(ImageChops.multiply(bar.getchannel("A"), mask))
        im.alpha_composite(bar, BAR_BOX[:2])

    digits = [_digit(card, d) for d in str(level)]
    total_w = sum(d.width for d in digits) + DIGIT_KERNING * (len(digits) - 1)
    x = DIGIT_CENTER_X - total_w // 2
    for d in digits:
        im.alpha_composite(d, (x, DIGIT_TOP))
        x += d.width + DIGIT_KERNING

    for badge_set, slot in badges:
        im.alpha_composite(_badge(badge_set, slot))

    out = BytesIO()
    im.save(out, format="PNG")
    out.seek(0)
    return out
