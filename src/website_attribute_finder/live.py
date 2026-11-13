"""One live run: rows in, pages captured and tagged, the engine scores them."""

import base64
import csv
import io
import json
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from attribute_engine.discover import build_prompt, call_claude, parse_attributes
from attribute_engine.stats import scorecard
from dotenv import load_dotenv
from PIL import Image
from playwright.sync_api import sync_playwright

from . import analyze, attributes, capture, page_measures, run_store, safety, storage, tagging, tokens

MAX_PAGES = 25
MIN_PAGES = 4
CAPTURE_WORKERS = 3
PAGE_TYPE = "page"
SHOT_WIDTH = {"fold": 1440, "full": 1000}
SHOT_MAX_HEIGHT = 9000
SAMPLE_BANNER = "Illustrative data. Not real analytics."


class BadInput(ValueError):
    pass


def parse_rate(text):
    """12.3% and 0.123 are the same rate. Any other number is taken as it stands."""
    clean = text.strip().replace(",", "")
    percent = clean.endswith("%")
    try:
        value = float(clean.rstrip("%"))
    except ValueError:
        raise BadInput(f"Not a number: {text}") from None
    return value / 100 if percent else value


def parse_rows(text):
    """A CSV with a url column and one metric column, in that order or any other."""
    table = list(csv.DictReader(io.StringIO(text.strip())))
    if not table:
        raise BadInput("Add at least one row under the header.")
    names = list(table[0])
    url_column = next((n for n in names if n and n.strip().lower() == "url"), None)
    metrics = [n for n in names if n and n != url_column]
    if not url_column or len(metrics) != 1:
        raise BadInput("Use two columns: url and your metric.")
    rows, seen = [], set()
    for line in table:
        url = (line[url_column] or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append({"url": url, "conversion_rate": parse_rate(line[metrics[0]] or "")})
    if not MIN_PAGES <= len(rows) <= MAX_PAGES:
        raise BadInput(f"Use {MIN_PAGES} to {MAX_PAGES} different URLs. This has {len(rows)}.")
    return rows, metrics[0].strip()


def run_config(client, selected, custom):
    """The catalog cut down to what this run asked for, plus the user's own."""
    config = tagging.load_config(client)
    wanted = [a for a in config["attributes"] if a["name"] in selected]
    config["attributes"] = wanted + [clean_custom(a) for a in custom]
    return config


def clean_custom(attr):
    name = re.sub(r"[^a-z0-9]+", "_", str(attr.get("name", "")).lower()).strip("_")
    question = str(attr.get("question", "")).strip()
    if not name or not question:
        raise BadInput("Each attribute needs a name and a question.")
    base = {"name": name[:40], "title": str(attr.get("title") or name)[:60], "question": question[:300],
            "computed_by": "jev", "group": "Yours"}
    if attr.get("type") == "boolean":
        return {**base, "type": "boolean", "true": "yes", "false": "no"}
    options = {str(k)[:40]: str(v)[:200] for k, v in (attr.get("options") or {}).items()}
    if not 2 <= len(options) <= 6:
        raise BadInput(f"{base['title']} needs 2 to 6 options.")
    return {**base, "type": "choice", "options": options}


def block_private(route):
    """Checked on every request, so a redirect cannot reach anything internal."""
    host = re.sub(r"^https?://", "", route.request.url).split("/")[0].split(":")[0]
    if safety.is_public_host(host):
        route.continue_()
    else:
        route.abort()


def capture_group(rows, run_id, pattern, report):
    done = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=capture.VIEWPORT, reduced_motion="reduce")
        page.route("**/*", block_private)
        for row in rows:
            name = uuid.uuid4().hex[:12]
            try:
                got = capture.render(page, row["url"], run_id, name, pattern)
                done.append({**row, **got, "source": "live", "page_type": PAGE_TYPE,
                             "captured_at": datetime.now(timezone.utc).strftime("%Y%m%d")})
            except Exception as err:
                print(f"Skipped {row['url']}: {err}", flush=True)
            report(row["url"])
        browser.close()
    return done


def capture_all(rows, run_id, pattern, report):
    groups = [rows[i::CAPTURE_WORKERS] for i in range(CAPTURE_WORKERS)]
    with ThreadPoolExecutor(max_workers=CAPTURE_WORKERS) as pool:
        results = pool.map(lambda group: capture_group(group, run_id, pattern, report), groups)
    return [row for group in results for row in group]


def add_measures(row, run_id, config):
    counts = row["elements"]
    headline = row["rendered_headline"] or row["text"].strip().split("\n")[0][:160]
    out = {**row, "headline": headline, **attributes.measure(row, config["cta_patterns"]),
           "image_count": counts["image_count"], "video_count": counts["video_count"],
           "section_count": counts["section_count"], "jev_video_on_page": counts["video_on_page"],
           "jev_form_on_page": counts["form_on_page"], **page_measures.cta_look(storage.run_dir(run_id) / row["fold_screenshot"], row["cta_style"]),
           **page_measures.measure(row, run_id, config, headline)}
    if "jev_sentiment_weights" in row:
        out["sentiment"] = page_measures.sentiment_score(json.loads(row["jev_sentiment_weights"]))
    return out


def page_id(index):
    return f"p{index + 1}"


def shot_bytes(path, width):
    image = Image.open(path).convert("RGB")
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)))
    buffer = io.BytesIO()
    image.crop((0, 0, image.width, min(image.height, SHOT_MAX_HEIGHT))).save(buffer, "JPEG", quality=72)
    return buffer.getvalue()


def public_row(row, index, shots, pattern):
    drop = ("text", "clickable_labels", "fold_screenshot", "full_screenshot", "elements", "cta_style",
            "rendered_headline")
    return {**{k: v for k, v in row.items() if k not in drop and not k.endswith("_weights")},
            "id": page_id(index), "opening": row["headline"], "fold_shot": shots[0], "full_shot": shots[1],
            "ctas": attributes.cta_labels(row["clickable_labels"], pattern)}


def attribute_labels(config):
    return [{"name": a["name"], "title": a.get("title"), "question": a.get("question", ""),
             "computed_by": a["computed_by"], "type": "number" if a.get("score_as_number") else a.get("type", "choice"),
             "group": a.get("group", "Yours"), "default": bool(a.get("default")), "options": a.get("options", {})}
            for a in config["attributes"]]


def execute(rows, metric, selected, custom, client, report, store_shot, words=True):
    """One run, with its working files removed however it ends."""
    run_id = uuid.uuid4().hex
    try:
        return execute_run(run_id, rows, metric, selected, custom, client, report, store_shot, words)
    finally:
        shutil.rmtree(storage.run_dir(run_id), ignore_errors=True)


def execute_run(run_id, rows, metric, selected, custom, client, report, store_shot, words):
    """Models never see the rows' metric; tagging ends before it is joined."""
    load_dotenv(".env")
    for row in rows:
        safety.check_url(row["url"])
    config = run_config(client, selected, custom)
    total = len(rows)
    captured = []

    def page_done(url):
        captured.append(url)
        report({"stage": "capture", "done": len(captured), "total": total})

    pages = capture_all(rows, run_id, config["cta_patterns"], page_done)
    if len(pages) < MIN_PAGES:
        raise BadInput("Too few of those pages could be opened.")
    report({"stage": "tag", "done": 0, "total": len(pages)})
    metrics = {p["url"]: p.pop("conversion_rate") for p in pages}
    tagged = tagging.tag(pages, run_id, config)
    measured = [add_measures(p, run_id, config) for p in tagged]
    for row in measured:
        row["conversion_rate"] = metrics[row["url"]]
    report({"stage": "score", "done": len(measured), "total": len(measured)})
    return score(run_id, measured, metric, config, total, store_shot, words)


def score(run_id, measured, metric, config, total, store_shot, words=True):
    """Measured rows with their metric in, the viewer's result out. Code only."""
    engine = analyze.stats_config(config)
    card = scorecard(measured, engine)
    table = tokens.analyze(measured, {**config["tokens"], "min_pages": max(2, round(len(measured) / 3))}) if words else None
    folder = storage.run_dir(run_id)
    public = []
    for index, row in enumerate(measured):
        shots = [store_shot(run_id, f"{page_id(index)}-{kind}.jpg",
                            shot_bytes(folder / row[f"{kind}_screenshot"], SHOT_WIDTH[kind]))
                 for kind in ("fold", "full")]
        public.append(public_row(row, index, shots, config["cta_patterns"]))
    cost = sum(float(r.get(k, 0) or 0) for r in measured
               for k in ("jev_billed_cost_usd", "vision_cost_usd", "vision_page_cost_usd"))
    return {"run_id": run_id, "metric": metric, "pages": public, "skipped": total - len(measured),
            "scorecards": {PAGE_TYPE: {"rows": len(measured), "card": card}},
            "words": {PAGE_TYPE: table} if table else {}, "attributes": attribute_labels(config),
            "cost_usd": round(cost, 4)}


def ideas(text, count, selected, custom, client):
    """Blind discovery: Claude reads page copy and never the metric column."""
    load_dotenv(".env")
    rows, _ = parse_rows(text)
    config = run_config(client, selected, custom)

    def copy_of(row):
        safety.check_url(row["url"])
        response = requests.get(row["url"], timeout=20, allow_redirects=False,
                                headers={"User-Agent": "Mozilla/5.0"})
        return capture.read_copy(response.text)[:config["discovery_chars"]]

    with ThreadPoolExecutor(max_workers=5) as pool:
        texts = [t for t in pool.map(copy_of, rows[:12]) if t.strip()]
    config["discovery"] = {**config["discovery"], "max_attributes": max(1, min(int(count), 8))}
    reply, _, _ = call_claude(build_prompt(config, texts), config["discovery"]["model"],
                              os.environ.get("AI_GATEWAY_API_KEY"))
    found = parse_attributes(reply, config["discovery"]["max_attributes"])
    out = []
    for a in found:
        if a.get("name") and a.get("question") and a.get("type") in ("boolean", "choice"):
            out.append({"name": a["name"], "title": a["name"].replace("_", " ").capitalize(),
                        "question": a["question"], "type": a["type"], "options": a.get("options") or {}})
    return out


MEASURE_TEXT_CHARS = 5000
MEASURE_SHOT_WIDTH = 720


def measure_pages(urls, client):
    """Open pages and measure them, with no AI: for an assistant that tags the pages itself.

    Returns each page's text, the top-of-page screenshot (a small JPEG), the code measures
    (word count, reading grade, CTA count...) and the code-read labels (CTA wording, form,
    colors). Nothing is kept: the working files go when it ends.
    """
    for url in urls:
        safety.check_url(url)
    config = tagging.load_config(client)
    code = [a["name"] for a in config["attributes"] if a["computed_by"] == "code"]
    labels = [a["name"] for a in config["attributes"] if a["computed_by"] == "label"]
    run_id = uuid.uuid4().hex
    try:
        pages = capture_all([{"url": u} for u in urls], run_id, config["cta_patterns"], lambda _: None)
        out = []
        for page in pages:
            try:
                row = add_measures({**page, "render_ok": True}, run_id, config)
            except Exception as err:
                print(f"Measure failed for {page['url']}: {err}", flush=True)
                row = page
            image = Image.open(storage.run_dir(run_id) / page["fold_screenshot"]).convert("RGB")
            if image.width > MEASURE_SHOT_WIDTH:
                image = image.resize((MEASURE_SHOT_WIDTH, round(image.height * MEASURE_SHOT_WIDTH / image.width)))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=65)
            out.append({
                "url": page["url"],
                "headline": row.get("headline") or page.get("rendered_headline"),
                "text": page["text"][:MEASURE_TEXT_CHARS],
                "measures": {n: row[n] for n in code if n in row and row[n] is not None},
                "labels": {n: row[f"jev_{n}"] for n in labels if row.get(f"jev_{n}") is not None},
                "screenshot_jpeg_base64": base64.b64encode(buffer.getvalue()).decode(),
            })
        missing = [u for u in urls if u not in {p["url"] for p in pages}]
        return {"pages": out, "could_not_open": missing}
    finally:
        shutil.rmtree(storage.run_dir(run_id), ignore_errors=True)


def catalog(client):
    config = tagging.load_config(client)
    return attribute_labels(config)


def publish_sample(client):
    """The ready-made result visitors see before they change anything."""
    root = Path("config") / client
    text = (root / "sample.csv").read_text()
    rows, metric = parse_rows(text)
    config = tagging.load_config(client)
    selected = [a["name"] for a in config["attributes"] if a.get("default")]
    shots = Path("web/public/shots")
    shots.mkdir(parents=True, exist_ok=True)
    for old in shots.iterdir():
        old.unlink()

    def store(_, name, data):
        (shots / name).write_bytes(data)
        return f"/shots/{name}"

    result = execute(rows, metric, selected, [], client, lambda e: print(e, flush=True), store)
    write_viewer(client, result, text)
    print(f"{len(result['pages'])} pages, ${result['cost_usd']}", flush=True)


def write_viewer(client, result, sample_csv, web=Path("web")):
    """The two files the viewer reads: the sample result and the attribute catalog."""
    data = web / "src" / "data"
    data.mkdir(parents=True, exist_ok=True)
    result = {**result, "sample": True, "banner": SAMPLE_BANNER}
    json.dump(result, open(data / "results.json", "w"), default=str)
    json.dump({"attributes": catalog(client), "sample_csv": sample_csv, "max_pages": MAX_PAGES},
              open(data / "catalog.json", "w"))
    return result
