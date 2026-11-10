"""URL list to results. Paid steps are cached, so reruns are fast and free."""

import json
import os
import random
import time

from dotenv import load_dotenv

from attribute_engine.discover import build_prompt, call_claude, parse_attributes

from . import analyze, attributes, capture, export, page_measures, simulate, storage, tagging

BANNER = "Illustrative data. Not real analytics."


def merged_pages(client):
    """Archive plus live. A last archived version that matches live is the same page."""
    site = capture.load_site(client)
    threshold = site["archive"]["same_copy_similarity"]
    live = storage.read_rows(client, "live_pages")
    by_url = {r["url"]: r for r in live}
    archive = sorted(storage.read_rows(client, "archive_pages"),
                     key=lambda r: (r["url"], r["captured_at"]))
    keep = []
    for i, row in enumerate(archive):
        is_last = i + 1 == len(archive) or archive[i + 1]["url"] != row["url"]
        current = by_url.get(row["url"])
        if is_last and current and not capture.is_new_version(row["text"], current["text"], threshold):
            continue
        keep.append(row)
    if site.get("analyze") == "live":
        return live
    return keep + live


def valid_attribute(attr):
    if not isinstance(attr, dict) or not attr.get("name") or not attr.get("question"):
        return False
    if attr.get("type") == "choice":
        return isinstance(attr.get("options"), dict) and len(attr["options"]) >= 2
    return attr.get("type") == "boolean"


def discovered_attributes(client, config, pages):
    cached = storage.read_rows(client, "discovered")
    if cached:
        return cached
    load_dotenv(".env")
    d = config["discovery"]
    texts = [p["text"][:config["discovery_chars"]] for p in pages]
    texts = random.Random(0).sample(texts, min(len(texts), d["sample_size"]))
    reply, tokens_in, tokens_out = call_claude(
        build_prompt(config, texts), d["model"], os.environ.get("AI_GATEWAY_API_KEY"))
    proposed = parse_attributes(reply, d["max_attributes"])
    approved = [{k: v for k, v in a.items() if k != "why"} for a in proposed if valid_attribute(a)]
    skipped = len(proposed) - len(approved)
    print(f"Discovery: {len(approved)} kept, {skipped} malformed, {tokens_in}/{tokens_out} tokens",
          flush=True)
    storage.write_rows(client, "discovered", approved)
    return approved


def tagged_pages(client, config, pages):
    cached = {(r["url"], r["captured_at"]): r for r in storage.read_rows(client, "tagged")}
    todo = [p for p in pages if (p["url"], p["captured_at"]) not in cached]
    if todo:
        for row in tagging.tag(todo, client, config):
            cached[(row["url"], row["captured_at"])] = row
        storage.write_rows(client, "tagged", list(cached.values()))
    elements = {(r["url"], r["captured_at"]): r for r in storage.read_rows(client, "page_elements")}
    out = []
    for page in pages:
        key = (page["url"], page["captured_at"])
        row = {**cached[key], **page}
        counts = {("jev_" + k if k in ("video_on_page", "form_on_page") else k): v
                  for k, v in elements[key].items()}
        out.append({**row, **attributes.measure(row, config["cta_patterns"]), **counts,
                    **page_measures.measure(row, client, config, headline(row))})
    return out


def attribute_labels(config):
    return [{"name": a["name"], "title": a.get("title"), "question": a.get("question", ""),
             "computed_by": a["computed_by"], "type": a.get("type", "choice"),
             "group": a.get("group", "AI suggested"), "default": bool(a.get("default")),
             "options": a.get("options", {})} for a in config["attributes"]]


def opening(text):
    """The first real sentence or headline, skipping nav labels."""
    lines = [line.strip() for line in text.splitlines() if len(line.strip().split()) >= 4]
    return (lines[0] if lines else text.strip())[:160]


CTA = [""]


def headline(row):
    return row.get("headline") or opening(row["text"])


def public_row(row):
    drop = ("text", "clickable_labels", "fold_screenshot", "full_screenshot")
    return {**{k: v for k, v in row.items() if k not in drop and not k.endswith("_weights")},
            "id": export.page_id(row), "opening": headline(row),
            "ctas": attributes.cta_labels(row["clickable_labels"], CTA[0]),
            "fold_shot": export.shot_url(row["fold_screenshot"]),
            "full_shot": export.shot_url(row["full_screenshot"])}


def cost_summary(rows):
    report = tagging.cost_report(rows)
    return {"rows": report["rows"], "total_usd": report["jev_billed"] + report["vision_cost"]}


def timeline_view(rows, url, config):
    versions = sorted((r for r in rows if r["url"] == url), key=lambda r: r["captured_at"])
    return [{**step, "id": export.page_id(r), "opening": headline(r),
             "ctas": attributes.cta_labels(r["clickable_labels"], config["cta_patterns"]),
             "render_ok": r["render_ok"], "fold_shot": export.shot_url(r["fold_screenshot"])}
            for step, r in zip(analyze.timeline(rows, url, config), versions)]


def run(client):
    started = time.perf_counter()
    config = tagging.load_config(client)
    # Live-only attributes were never tagged on saved pages.
    config["attributes"] = [a for a in config["attributes"] if not a.get("live_only")]
    pages = merged_pages(client)
    found = discovered_attributes(client, config, pages)
    config["attributes"] = config["attributes"] + found
    rows = tagged_pages(client, config, pages)
    settings = simulate.load_settings(client)
    rows = simulate.simulate(rows, settings)
    CTA[0] = config["cta_patterns"]
    cards = analyze.scorecards(rows, config)
    multi = sorted({r["url"] for r in rows if sum(x["url"] == r["url"] for x in rows) > 1})
    result = {"client": client, "banner": BANNER, "pages": [public_row(r) for r in rows],
              "scorecards": cards, "words": analyze.word_tables(rows, config["tokens"]),
              "timelines": {u: timeline_view(rows, u, config) for u in multi},
              "attributes": attribute_labels(config), "planted": analyze.recovered(settings["planted_effects"], cards),
              "cost": cost_summary(rows), "metric_source": simulate.METRIC_SOURCE}
    path = storage.run_dir(client) / "results.json"
    json.dump(result, open(path, "w"), indent=1, default=str)
    export.publish(client, result, rows)
    print(f"{len(rows)} page versions, {len(multi)} URLs with history, "
          f"{time.perf_counter() - started:.1f}s", flush=True)
    return result
