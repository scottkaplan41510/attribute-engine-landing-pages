"""The illustrative sample: a made-up company, drawn pages, planted effects.

Runs offline with no keys. The tags come from config/<client>/illustrative_pages.yaml
instead of an AI model, and the metric is simulated, so everything it shows is
illustrative. The scoring is the same code a real run uses.
"""

import textwrap
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

from . import live, simulate, storage, tagging

WIDTH, FOLD, LENGTH = 1440, 900, 2400
PAPER, LINE, TEXT, SOFT = (248, 248, 247), (222, 222, 220), (34, 34, 36), (150, 150, 152)
BUTTONS = {"high": ((20, 20, 22), (300, 76)), "medium": ((120, 120, 124), (230, 60)),
           "low": ((228, 228, 226), (170, 44))}


def font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow before 10.1 has one fixed size
        return ImageFont.load_default()


def draw_hero(d, style):
    """A placeholder for what dominates the top of the page."""
    x0, y0, x1, y1 = 820, 170, 1360, 720
    if style == "product_ui":
        d.rectangle((x0, y0, x1, y1), fill=(255, 255, 255), outline=LINE, width=3)
        d.rectangle((x0, y0, x1, y0 + 44), fill=LINE)
        for i in range(5):
            top = y0 + 80 + i * 92
            d.rectangle((x0 + 30, top, x0 + 30 + 120 + (i % 3) * 110, top + 52), fill=(232, 232, 230))
    elif style == "people":
        for i, cx in enumerate((930, 1090, 1250)):
            cy = 360 + (i % 2) * 60
            d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=(196, 196, 194))
            d.rounded_rectangle((cx - 90, cy + 75, cx + 90, cy + 300), 60, fill=(210, 210, 208))
    elif style == "abstract":
        d.ellipse((x0, y0, x0 + 360, y0 + 360), fill=(214, 214, 212))
        d.rectangle((x0 + 200, y0 + 220, x1, y1), fill=(186, 186, 184))
        d.polygon([(x0 + 40, y1), (x0 + 260, y0 + 300), (x0 + 480, y1)], fill=(232, 232, 230))
    # text_only: nothing but the copy


def draw_page(page, company, folder, name):
    """A full page and its top screen. Returns the main button's box, if any."""
    image = Image.new("RGB", (WIDTH, LENGTH), PAPER)
    d = ImageDraw.Draw(image)
    d.text((80, 36), company, fill=TEXT, font=font(28))
    for i, label in enumerate(page["ctas"][1:3]):
        d.text((1000 + i * 170, 42), label, fill=SOFT, font=font(20))
    d.line((0, 100, WIDTH, 100), fill=LINE, width=2)
    d.text((80, 190), page["headline"], fill=TEXT, font=font(52))
    lines = textwrap.wrap(" ".join(page["copy"].split()), 50)
    for i, line in enumerate(lines[:4]):
        d.text((80, 290 + i * 40), line, fill=SOFT, font=font(24))
    box = None
    look = BUTTONS.get(page["tags"]["cta_prominence"])
    if look:
        color, (w, h) = look
        box = {"x": 80, "y": 530, "width": w, "height": h}
        d.rounded_rectangle((80, 530, 80 + w, 530 + h), h // 2, fill=color)
        d.text((110, 530 + h // 2 - 12), page["ctas"][0], font=font(24),
               fill=(255, 255, 255) if color[0] < 150 else TEXT)
    draw_hero(d, page["tags"]["hero_style"])
    d.text((80, FOLD - 60), "Illustrative page. Example Co is made up.", fill=SOFT, font=font(18))
    for i in range(3):
        top = FOLD + 200 + i * 420
        d.rectangle((80, top, WIDTH - 80, top + 300), outline=LINE, width=2)
    shots = folder / "screenshots"
    image.save(shots / f"{name}-full.png")
    image.crop((0, 0, WIDTH, FOLD)).save(shots / f"{name}-fold.png")
    return box


def build(client, web=Path("web")):
    source = yaml.safe_load(open(Path("config") / client / "illustrative_pages.yaml"))
    config = tagging.load_config(client)
    config["attributes"] = [a for a in config["attributes"] if a.get("default")]
    run_key = f"{client}-illustrative"
    folder = storage.run_dir(run_key)
    rows = []
    for i, page in enumerate(source["pages"]):
        name = f"p{i + 1}"
        box = draw_page(page, source["company"], folder, name)
        row = {"url": source["base_url"] + page["path"], "captured_at": "20260101",
               "source": "illustrative", "page_type": live.PAGE_TYPE, "render_ok": True,
               "text": f"{page['headline']}\n{page['copy']}", "clickable_labels": page["ctas"],
               "rendered_headline": page["headline"], "cta_style": box,
               "elements": {"image_count": 3, "video_count": 0, "section_count": 4,
                            "video_on_page": "none", "form_on_page": "no"},
               "fold_screenshot": f"screenshots/{name}-fold.png",
               "full_screenshot": f"screenshots/{name}-full.png",
               **{f"jev_{k}": v for k, v in page["tags"].items()}}
        rows.append(live.add_measures(row, run_key, config))
    rows = [{k: v for k, v in r.items() if k != "weeks"}
            for r in simulate.simulate(rows, simulate.load_settings(client))]

    shots = web / "public" / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    for old in shots.iterdir():
        old.unlink()

    def store(_, name, data):
        (shots / name).write_bytes(data)
        return f"/shots/{name}"

    result = live.score(run_key, rows, "conversion_rate", config, len(rows), store)
    sample_csv = "url,conversion_rate\n" + "".join(
        f"{p['url']},{p['conversion_rate'] * 100:.2f}%\n" for p in result["pages"])
    (Path("config") / client / "sample.csv").write_text(sample_csv)
    return live.write_viewer(client, result, sample_csv, web)
