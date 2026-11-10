"""Tag page versions: code, then Jev on copy, then vision on screenshots."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from attribute_engine.tag import tag_rows as jev_tag_rows

from . import attributes, storage, vision


def load_config(client):
    return yaml.safe_load(open(Path("config") / client / "attributes.yaml"))


def tag(rows, client, config):
    load_dotenv(".env")
    limit = config["settings"]["max_copy_chars"]
    # Jev keeps nothing but copy here: no url, no metric, no other columns.
    prepared = [{"copy": r["text"][:limit], "_i": i} for i, r in enumerate(rows)]
    jev_config = {**config, "attributes": [a for a in config["attributes"]
                                           if a["computed_by"] == "jev"]}
    jev = (jev_tag_rows(prepared, jev_config, os.environ.get("AI_GATEWAY_API_KEY"))
           if jev_config["attributes"] else [{} for _ in rows])
    seen = vision.tag_rows(rows, client, config)
    out = []
    for row, j, v in zip(rows, jev, seen):
        extra = {k: x for k, x in j.items() if k not in ("copy", "_i", "word_count")}
        out.append({**row, **attributes.measure(row, config["cta_patterns"]), **extra, **v})
    return out


def cost_report(rows):
    jev = sum(r.get("jev_billed_cost_usd", 0) for r in rows)
    jev_market = sum(r.get("jev_market_cost_usd", 0) for r in rows)
    vis_cost = sum(r.get("vision_cost_usd", 0) for r in rows)
    vis_in = sum(r.get("vision_input_tokens", 0) for r in rows)
    vis_out = sum(r.get("vision_output_tokens", 0) for r in rows)
    return {"rows": len(rows), "jev_billed": jev, "jev_market": jev_market, "vision_cost": vis_cost,
            "vision_input_tokens": vis_in, "vision_output_tokens": vis_out}


def tag_sample(client, urls):
    config = load_config(client)
    rows = [r for r in storage.read_rows(client, "live_pages") if r["url"] in urls]
    tagged = tag(rows, client, config)
    storage.write_rows(client, "tag_sample", tagged)
    return tagged
