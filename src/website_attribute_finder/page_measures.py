"""Attributes measured free from what capture already saved. No model, no metric."""

import colorsys
import re

from PIL import Image

from . import attributes, storage
from .vision import UNKNOWN

SCREEN_HEIGHT = 900
SAMPLE_WIDTH = 120
MIX_BELOW = 0.4
HUES = [(15, "red"), (45, "orange"), (70, "yellow"), (170, "green"), (255, "blue"),
        (300, "purple"), (345, "pink"), (360, "red")]


def color_family(r, g, b):
    hue, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if value < 0.2:
        return "black"
    if saturation < 0.15:
        return "white" if value > 0.9 else "grey"
    return next(name for edge, name in HUES if hue * 360 <= edge)


def colors(path):
    image = Image.open(path).convert("RGB")
    height = max(1, round(image.height * SAMPLE_WIDTH / image.width))
    pixels = list(image.resize((SAMPLE_WIDTH, height)).getdata())
    shares = {}
    for pixel in pixels:
        family = color_family(*pixel)
        shares[family] = shares.get(family, 0) + 1 / len(pixels)
    top = max(shares, key=shares.get)
    brightness = sum(sum(p) for p in pixels) / (3 * 255 * len(pixels))
    return {"jev_primary_color": top if shares[top] >= MIX_BELOW else "mix",
            "jev_background": "light" if brightness >= 0.5 else "dark",
            "page_length": round(image.height / SCREEN_HEIGHT, 1)}


def luminance(rgb):
    def channel(value):
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio, 1 to 21."""
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return round((light + 0.05) / (dark + 0.05), 1)


def cta_look(path, box):
    """Read the button's fill just inside its left edge, and what is just outside it."""
    if not box:
        return {"jev_cta_color": "none", "cta_contrast": 1.0}
    image = Image.open(path).convert("RGB")
    middle = round(box["y"] + box["height"] / 2)
    fill = image.getpixel((round(box["x"]) + 8, middle))
    behind = image.getpixel((max(round(box["x"]) - 8, 0), middle))
    return {"jev_cta_color": color_family(*fill), "cta_contrast": contrast(fill, behind)}


def sentiment_score(weights):
    """Positive weight minus negative weight, -1 to +1."""
    return round(weights.get("positive", 0) - weights.get("negative", 0), 3)


def cta_wording(labels, config):
    found = attributes.cta_labels(labels, config["cta_patterns"])
    if not found:
        return "none"
    first = found[0].lower()
    return next((k for k, p in config["cta_wordings"].items() if re.search(p, first)), "other")


def measure(row, client, config, headline):
    path = storage.run_dir(client) / row["full_screenshot"]
    seen = colors(path)
    if not row.get("render_ok"):
        seen = {**seen, "jev_primary_color": UNKNOWN, "jev_background": UNKNOWN}
    return {**seen, "headline_length": len(headline.split()),
            "jev_cta_wording": cta_wording(row["clickable_labels"], config)}
