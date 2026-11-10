"""Capture page versions: live pages now, plus history from the Internet Archive.

One row per version of one page. A version only counts when the copy changed.
"""

import difflib
import html
import re
import subprocess
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import yaml
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from . import storage

VIEWPORT = {"width": 1440, "height": 900}
CDX = "https://web.archive.org/cdx/search/cdx"
READ_PAGE = """() => {
  document.querySelectorAll('nav, footer, script, style, noscript').forEach(e => e.remove());
  return document.body.innerText;
}"""


OFFLINE = "Temporarily Offline"
HEADLINE_HIDDEN = """() => {
  const h1 = document.querySelector('h1');
  if (!h1) return true;
  for (let el = h1; el; el = el.parentElement) {
    const style = getComputedStyle(el);
    if (style.opacity === '0' || style.visibility === 'hidden') return true;
  }
  return false;
}"""
# Rotating headlines stack once forced visible, so keep only the first line.
ONE_ROTATING_LINE = """() => {
  document.querySelectorAll('h1, h2').forEach(heading => {
    const box = heading.getBoundingClientRect();
    const stacked = [...heading.parentElement.children].filter(other => {
      const b = other.getBoundingClientRect();
      return other !== heading && other.tagName === heading.tagName
        && Math.abs(b.top - box.top) < 8;
    });
    stacked.forEach(other => { other.style.display = 'none'; });
  });
}"""
REVEAL = ("*{animation:none!important;transition:none!important}"
          "[style*='opacity:0'],[style*='opacity: 0']{opacity:1!important;transform:none!important}"
          "[style*='visibility:hidden']{visibility:visible!important}")


def load_site(client):
    return yaml.safe_load(open(Path("config") / client / "site.yaml"))


def normalize_path(url):
    path = re.sub(r"^https?://(www\.)?[^/]+", "", url)
    path = re.sub(r"[?#].*", "", path).rstrip("/")
    return path or "/"


def page_type(path, site):
    return "content" if re.search(site["content_pattern"], path) else "marketing"


def similarity(a, b):
    return difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()


def is_new_version(previous_text, text, threshold):
    return previous_text is None or similarity(previous_text, text) < threshold


def slug(path, stamp):
    name = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
    return f"{name}-{stamp}"


# Where the main button sits on screen. Its colors come from the screenshot, since
# a gradient or image behind a button has no color in the page's code.
CTA_STYLE = """(pattern) => {
  const re = new RegExp(pattern, 'i');
  const box = [...document.querySelectorAll('a, button')]
    .filter(e => re.test(e.innerText || ''))
    .map(e => e.getBoundingClientRect())
    .find(b => b.height > 20 && b.left > 20 && b.top >= 0 && b.bottom < innerHeight);
  return box ? { x: box.left, y: box.top, width: box.width, height: box.height } : null;
}"""


def read_labels(page):
    labels = page.evaluate(
        """() => [...document.querySelectorAll('a, button')]
            .map(e => (e.innerText || '').trim()).filter(t => t && t.length < 40)"""
    )
    return sorted(set(labels))


def render(page, url, client, name, cta_pattern=None):
    """Open a page, scroll so lazy content loads, screenshot, read the copy."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    height = page.evaluate("document.body.scrollHeight")
    for y in range(0, height, 450):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(450)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)
    shots = storage.run_dir(client) / "screenshots"
    page.screenshot(path=shots / f"{name}-fold.png")
    page.screenshot(path=shots / f"{name}-full.png", full_page=True)
    links = read_labels(page)
    raw = page.content()
    style = page.evaluate(CTA_STYLE, cta_pattern) if cta_pattern else None
    text = re.sub(r"\n{3,}", "\n\n", page.evaluate(READ_PAGE)).strip()
    return {"text": text, "words": len(text.split()), "clickable_labels": links,
            "elements": count_elements(raw), "rendered_headline": first_heading(raw), "cta_style": style,
            "fold_screenshot": f"screenshots/{name}-fold.png",
            "full_screenshot": f"screenshots/{name}-full.png"}


def capture_live(client):
    site = load_site(client)
    now = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, reduced_motion="reduce")
        for path in site["live_pages"]:
            clean = normalize_path(path)
            try:
                got = render(page, site["base_url"] + path, client, slug(clean, now))
            except Exception as err:
                print(f"FAILED {clean}: {err}", flush=True)
                continue
            rows.append({"url": clean, "captured_at": now, "source": "live",
                         "page_type": page_type(clean, site),
                         "headline": first_heading(curl(site["base_url"] + path)), **got})
            print(clean, got["words"], "words", flush=True)
        browser.close()
    return storage.write_rows(client, "live_pages", rows), rows


def curl(url, timeout=45):
    out = subprocess.run(["curl", "-sL", "--compressed", "--max-time", str(timeout), url],
                         capture_output=True).stdout
    return out.decode("utf-8", "replace")


def archived_versions(site):
    """Distinct stored captures per path, oldest first. Same digest = same bytes."""
    a = site["archive"]
    query = (f"{CDX}?url={site['domain']}&matchType=domain&output=txt"
             "&fl=original,timestamp,digest&filter=statuscode:200"
             f"&filter=mimetype:text/html&from={a['from']}")
    listing = ""
    for attempt in range(4):
        listing = curl(query, 90)
        if listing.strip():
            break
        time.sleep(15 * (attempt + 1))
    if not listing.strip():
        raise RuntimeError("Internet Archive index came back empty")
    found = {}
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        original, stamp, digest = parts
        host = re.sub(r"^https?://(www\.)?", "", original).split("/")[0].replace(":80", "")
        path = normalize_path(original)
        if host != site["domain"] or re.search(a["skip_pattern"], path) or path in a["list_pages"]:
            continue
        found.setdefault(path, {}).setdefault(digest, (stamp, original))
    return {path: sorted(v.values()) for path, v in found.items()}


def stored_url(stamp, original):
    """The page as stored, so its scripts and images load from where they first lived."""
    return f"https://web.archive.org/web/{stamp}id_/{original}"


class CopyReader(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "nav", "footer", "head"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        data = re.sub(r"\s+", " ", data).strip()
        if data and not self.depth:
            self.parts.append(data)


def read_copy(raw_html):
    reader = CopyReader()
    reader.feed(raw_html)
    return html.unescape("\n".join(reader.parts))


def first_heading(raw_html):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, re.S | re.I)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1)))).strip()


def count_elements(raw_html, min_image_px=48):
    """What is in the page's code. Icons, inline images and tracking pixels are skipped."""
    images = 0
    for tag in re.findall(r"<img\b[^>]*>", raw_html, re.I):
        src = re.search(r"\bsrc=[\"']([^\"']*)", tag, re.I)
        width = re.search(r"\bwidth=[\"']?(\d+)", tag, re.I)
        if not src or src.group(1).startswith("data:") or ".svg" in src.group(1).lower():
            continue
        if width and int(width.group(1)) < min_image_px:
            continue
        images += 1
    videos = list(re.finditer(r"<video\b|<iframe\b[^>]*(youtube|vimeo|wistia|loom)", raw_html, re.I))
    if not videos:
        where = "none"
    else:
        where = "top" if videos[0].start() < len(raw_html) / 3 else "lower"
    return {"image_count": images, "video_count": len(videos), "video_on_page": where,
            "section_count": len(re.findall(r"<section\b", raw_html, re.I)),
            "form_on_page": "yes" if re.search(r"<form\b", raw_html, re.I) else "no"}


def is_offline(text):
    return not text or OFFLINE in text


def fetch_stored(stamp, original, tries=8):
    """The Archive drops out for short stretches, so wait it out."""
    for attempt in range(tries):
        raw = curl(stored_url(stamp, original))
        if not is_offline(raw) and "<" in raw[:300]:
            return raw
        time.sleep(min(10 * (attempt + 1), 45))
    return None


def headline_hidden(page):
    return page.evaluate(HEADLINE_HIDDEN)


def render_stored(page, stamp, original, client, name, text, tries=6):
    """Screenshot a stored page. Reveal hidden content only if it would be blank."""
    for attempt in range(tries):
        response = page.goto(stored_url(stamp, original), wait_until="domcontentloaded", timeout=60000)
        if response.status < 500 and not is_offline(page.content()):
            break
        page.wait_for_timeout(min(10000 * (attempt + 1), 45000))
    else:
        return None
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        pass
    page.wait_for_timeout(1000)
    if headline_hidden(page):
        page.add_style_tag(content=REVEAL)
        page.evaluate(ONE_ROTATING_LINE)
        page.wait_for_timeout(800)
    shots = storage.run_dir(client) / "screenshots"
    page.screenshot(path=shots / f"{name}-fold.png")
    page.screenshot(path=shots / f"{name}-full.png", full_page=True)
    return {"text": text, "words": len(text.split()), "clickable_labels": read_labels(page),
            "fold_screenshot": f"screenshots/{name}-fold.png",
            "full_screenshot": f"screenshots/{name}-full.png"}


def capture_archive(client):
    site = load_site(client)
    a = site["archive"]
    plan = archived_versions(site)
    print(len(plan), "archived URLs", flush=True)
    done = {(r["url"], r["captured_at"]): r for r in storage.read_rows(client, "archive_pages")}
    rows = list(done.values())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        for path, captures in sorted(plan.items()):
            last_text = None
            for stamp, original in captures:
                day = stamp[:8]
                if (path, day) in done:
                    last_text = done[(path, day)]["text"]
                    continue
                raw = fetch_stored(stamp, original)
                time.sleep(1)
                if raw is None:
                    print(path, day, "UNREACHABLE", flush=True)
                    continue
                text = read_copy(raw)
                if len(text.split()) < a["min_words"]:
                    print(path, day, "no readable copy", flush=True)
                    continue
                if not is_new_version(last_text, text, a["same_copy_similarity"]):
                    print(path, day, "same copy", flush=True)
                    continue
                got = render_stored(page, stamp, original, client, slug(path, day), text)
                if got is None:
                    print(path, day, "UNREACHABLE for screenshot", flush=True)
                    continue
                last_text = text
                rows.append({"url": path, "captured_at": day, "source": "archive",
                             "page_type": page_type(path, site), "archive_stamp": stamp,
                             "headline": first_heading(raw), **got})
                storage.write_rows(client, "archive_pages", rows)
                print(path, day, got["words"], "words NEW", flush=True)
        browser.close()
    return rows


def count_page_elements(client):
    """Count images, video and layout from each version's stored HTML. Free, and resumable."""
    site = load_site(client)
    done = {(r["url"], r["captured_at"]): r for r in storage.read_rows(client, "page_elements")}
    pages = storage.read_rows(client, "live_pages") + storage.read_rows(client, "archive_pages")
    for row in pages:
        if (row["url"], row["captured_at"]) in done:
            continue
        if row["source"] == "live":
            raw = curl(site["base_url"] + row["url"])
        else:
            raw = fetch_stored(row["archive_stamp"], f"https://{site['domain']}{row['url']}")
            time.sleep(0.5)
        if not raw:
            print("UNREACHABLE", row["url"], row["captured_at"], flush=True)
            continue
        done[(row["url"], row["captured_at"])] = {
            "url": row["url"], "captured_at": row["captured_at"], **count_elements(raw)}
        storage.write_rows(client, "page_elements", list(done.values()))
    return len(done), len(pages)


def backfill_headlines(client):
    """Add headlines to rows captured before they were stored."""
    site = load_site(client)
    live = storage.read_rows(client, "live_pages")
    for row in live:
        row["headline"] = first_heading(curl(site["base_url"] + row["url"]))
    storage.write_rows(client, "live_pages", live)
    archive = storage.read_rows(client, "archive_pages")
    for row in archive:
        if row.get("headline"):
            continue
        raw = fetch_stored(row["archive_stamp"], f"https://{site['domain']}{row['url']}")
        row["headline"] = first_heading(raw) if raw else ""
        time.sleep(0.5)
    storage.write_rows(client, "archive_pages", archive)
    return sum(1 for r in live + archive if r["headline"]), len(live + archive)


def reshoot_archive(client):
    """Screenshot stored pages again without changing their copy."""
    site = load_site(client)
    rows = storage.read_rows(client, "archive_pages")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        for row in rows:
            original = f"https://{site['domain']}{row['url']}"
            got = render_stored(page, row["archive_stamp"], original, client,
                                slug(row["url"], row["captured_at"]), row["text"])
            print(row["url"], row["captured_at"], "ok" if got else "UNREACHABLE", flush=True)
            if got:
                row["clickable_labels"] = got["clickable_labels"]
                storage.write_rows(client, "archive_pages", rows)
        browser.close()
