"""Hand simulated or real rows to the Attribute Finder engine. No stats live here."""

from attribute_engine.stats import scorecard

from . import tokens
from .vision import UNKNOWN


def stats_config(config):
    """The engine reads labels from jev_ columns, so vision tags use the same shape."""
    def shape(a):
        if a.get("score_as_number"):
            return {**a, "computed_by": "code", "type": "number"}
        return {**a, "computed_by": "jev"} if a["computed_by"] in ("vision", "label") else a
    return {**config, "attributes": [shape(a) for a in config["attributes"]]}


def combined_card(rows, engine):
    """The defaults are tested as their own small set. Anything added later is one more
    test, so it answers to a stricter bar and never changes the default results."""
    core = {**engine, "attributes": [a for a in engine["attributes"] if a.get("default")]}
    names = {a["name"] for a in core["attributes"]}
    if not names:
        return scorecard(rows, engine)
    return scorecard(rows, core) + [r for r in scorecard(rows, engine) if r["attribute"] not in names]


def scorecards(rows, config):
    """Marketing and content pages run apart so articles do not swamp product pages."""
    engine = stats_config(config)
    out = {}
    for kind in sorted({r["page_type"] for r in rows}):
        subset = [r for r in rows if r["page_type"] == kind]
        out[kind] = {"rows": len(subset), "card": combined_card(subset, engine)}
    return out


def word_tables(rows, settings):
    """Same split as the scorecards."""
    return {kind: tokens.analyze([r for r in rows if r["page_type"] == kind], settings)
            for kind in sorted({r["page_type"] for r in rows})}


def recovered(planted, cards):
    """Which planted effects the engine found again. Small samples miss some."""
    out = []
    for effect in planted:
        name = effect["attribute"].removeprefix("jev_")
        found = [r for c in cards.values() for r in c["card"]
                 if r["attribute"] == name and r["value"] == effect["value"] and r["significant"]]
        out.append({**effect, "found": bool(found)})
    return out


def timeline(rows, url, config):
    """All versions of one URL, oldest first, with what changed between them."""
    labels = [a["name"] for a in config["attributes"] if a["computed_by"] != "code"]
    versions = sorted((r for r in rows if r["url"] == url), key=lambda r: r["captured_at"])
    out, previous = [], None
    for r in versions:
        changed = []
        if previous:
            # A broken render is a gap in the record, not a change to the page.
            pairs = [(n, previous.get(f"jev_{n}"), r.get(f"jev_{n}")) for n in labels]
            changed = [{"attribute": n, "from": a, "to": b} for n, a, b in pairs
                       if a != b and UNKNOWN not in (a, b)]
        out.append({"captured_at": r["captured_at"], "conversion_rate": r["conversion_rate"],
                    "changed": changed, "fold_screenshot": r["fold_screenshot"]})
        previous = r
    return out
