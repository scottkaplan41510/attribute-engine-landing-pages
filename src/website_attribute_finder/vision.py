"""Tag the top-of-page screenshot. The model sees the image and nothing else."""

import base64
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

from . import storage

CHAT_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
UNKNOWN = "unknown"


def vision_attributes(config, scope="top"):
    return [a for a in config["attributes"]
            if a["computed_by"] == "vision" and a.get("scope", "top") == scope]


def build_prompt(attrs, intro="This is a screenshot of the top of a web page."):
    lines = [intro,
             "Answer each question with exactly one option key.",
             "Set render_ok to false if the page looks broken: missing styles,",
             "raw unstyled text, or mostly blank.", ""]
    for a in attrs:
        options = "; ".join(f"{k} = {v}" for k, v in a["options"].items())
        lines.append(f"{a['name']}: {a['question']} Options: {options}")
    keys = ", ".join(['"render_ok"'] + [f'"{a["name"]}"' for a in attrs])
    lines += ["", f"Return only JSON with keys {keys}."]
    return "\n".join(lines)


def parse_reply(reply, attrs):
    """Keep only valid options. A broken render gets unknown, never a guess."""
    body = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
    ok = bool(body.get("render_ok"))
    out = {"render_ok": ok}
    for a in attrs:
        value = str(body.get(a["name"])).lower() if ok else UNKNOWN
        out[f"jev_{a['name']}"] = value if value in a["options"] else UNKNOWN
    return out


def tag_one(row, client, attrs, model, key):
    path = storage.run_dir(client) / row["fold_screenshot"]
    image = base64.b64encode(open(path, "rb").read()).decode()
    payload = {"model": model, "max_tokens": 400, "messages": [{"role": "user", "content": [
        {"type": "text", "text": build_prompt(attrs)},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}}]}]}
    r = requests.post(CHAT_URL, json=payload, timeout=120,
                      headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        raise RuntimeError(f"Vision call failed ({r.status_code}): {r.text[:300]}")
    body = r.json()
    usage = body.get("usage", {})
    gateway = body.get("choices", [{}])[0].get("message", {}).get("provider_metadata", {})
    return {**parse_reply(body["choices"][0]["message"]["content"], attrs),
            "vision_input_tokens": usage.get("prompt_tokens", 0),
            "vision_output_tokens": usage.get("completion_tokens", 0),
            "vision_cost_usd": float(usage.get("cost", gateway.get("gateway", {}).get("cost", 0)) or 0)}


SLICE_WIDTH = 900
SLICE_HEIGHT = 1500
MAX_SLICES = 5
PAGE_INTRO = "These images are one full web page, top to bottom, in slices."


def page_slices(path):
    """A long page shrinks to nothing as one image, so send it in readable slices."""
    image = Image.open(path).convert("RGB")
    if image.width > SLICE_WIDTH:
        image = image.resize((SLICE_WIDTH, round(image.height * SLICE_WIDTH / image.width)))
    out = []
    for top in range(0, min(image.height, SLICE_HEIGHT * MAX_SLICES), SLICE_HEIGHT):
        buffer = io.BytesIO()
        image.crop((0, top, image.width, min(top + SLICE_HEIGHT, image.height))).save(buffer, "JPEG", quality=70)
        out.append(base64.b64encode(buffer.getvalue()).decode())
    return out


def tag_page(row, client, attrs, model, key):
    """Questions about the whole page, answered from slices of the full screenshot."""
    images = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{i}"}}
              for i in page_slices(storage.run_dir(client) / row["full_screenshot"])]
    payload = {"model": model, "max_tokens": 400, "messages": [{"role": "user", "content": [
        {"type": "text", "text": build_prompt(attrs, PAGE_INTRO)}, *images]}]}
    r = requests.post(CHAT_URL, json=payload, timeout=120, headers={"Authorization": f"Bearer {key}"})
    if r.status_code != 200:
        raise RuntimeError(f"Vision call failed ({r.status_code}): {r.text[:300]}")
    body = r.json()
    usage = body.get("usage", {})
    gateway = body.get("choices", [{}])[0].get("message", {}).get("provider_metadata", {})
    out = parse_reply(body["choices"][0]["message"]["content"], attrs)
    out.pop("render_ok")
    out["vision_page_cost_usd"] = float(usage.get("cost", gateway.get("gateway", {}).get("cost", 0)) or 0)
    return out


def tag_rows(rows, client, config):
    top, page = vision_attributes(config), vision_attributes(config, "page")
    if not top and not page:
        return [{"render_ok": True} for _ in rows]
    key = os.environ["AI_GATEWAY_API_KEY"]
    model = config["settings"]["vision_model"]

    def work(row):
        # The top-of-page call also reports whether the page rendered.
        seen = tag_one(row, client, top, model, key)
        return {**seen, **(tag_page(row, client, page, model, key) if page else {})}

    with ThreadPoolExecutor(max_workers=config["settings"]["concurrency"]) as pool:
        return list(pool.map(work, rows))
