"""Publish a history run next to the viewer. Screenshots become small JPEGs."""

import json
import re
from pathlib import Path

from PIL import Image

from . import storage

WEB = Path("web")
SHOT_WIDTH = {"fold": 1440, "full": 1000}
SHOT_MAX_HEIGHT = 9000


def page_id(row):
    name = re.sub(r"[^a-z0-9]+", "-", row["url"].lower()).strip("-") or "home"
    return f"{name}-{row['captured_at']}"


def shot_url(screenshot):
    return "/history-shots/" + Path(screenshot).with_suffix(".jpg").name


def save_shot(source, target, width):
    image = Image.open(source).convert("RGB")
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)))
    image.crop((0, 0, image.width, min(image.height, SHOT_MAX_HEIGHT))).save(target, quality=72)


def publish(client, result, rows):
    shots = WEB / "public" / "history-shots"
    shots.mkdir(parents=True, exist_ok=True)
    run = storage.run_dir(client)
    for row in rows:
        for kind in ("fold", "full"):
            shot = row[f"{kind}_screenshot"]
            target = shots / Path(shot).with_suffix(".jpg").name
            if (run / shot).stat().st_mtime > (target.stat().st_mtime if target.exists() else 0):
                save_shot(run / shot, target, SHOT_WIDTH[kind])
    used = {Path(row[f"{kind}_screenshot"]).with_suffix(".jpg").name for row in rows for kind in ("fold", "full")}
    for old in shots.iterdir():
        if old.name not in used:
            old.unlink()
    data = WEB / "src" / "data"
    data.mkdir(parents=True, exist_ok=True)
    # history.json, not results.json: the viewer's sample stays whatever `waf sample` wrote.
    json.dump(result, open(data / "history.json", "w"), default=str)
