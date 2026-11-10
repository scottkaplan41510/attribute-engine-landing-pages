"""Illustrative metrics: 12 weeks per page version, fixed seed, planted effects.

Reads attributes and page type only, never the copy. This is the one module to
replace when real analytics arrive; everything downstream reads the same fields.
"""

import zlib
from pathlib import Path

import numpy as np
import yaml

METRIC_SOURCE = "simulated"


def load_settings(client):
    return yaml.safe_load(open(Path("config") / client / "simulation.yaml"))


def true_rate(row, settings):
    rate = settings["base_rate"][row["page_type"]]
    for effect in settings["planted_effects"]:
        if row.get(effect["attribute"]) == effect["value"]:
            rate *= effect["multiplier"]
    return rate


def page_noise(url, settings):
    """One spread per URL, so versions of a page differ only through attributes."""
    rng = np.random.default_rng([settings["seed"], zlib.crc32(url.encode())])
    return float(rng.lognormal(0, settings["page_noise"]))


def simulate_row(row, settings, rng):
    rate = true_rate(row, settings) * page_noise(row["url"], settings)
    weeks = []
    for week in range(1, settings["weeks"] + 1):
        sessions = int(rng.poisson(settings["weekly_sessions"][row["page_type"]]))
        conversions = int(rng.binomial(sessions, min(rate, 1.0)))
        weeks.append({"week": week, "sessions": sessions, "conversions": conversions})
    sessions = sum(w["sessions"] for w in weeks)
    conversions = sum(w["conversions"] for w in weeks)
    # Attributes do not change within a version, so stats use one row per version.
    return {**row, "weeks": weeks, "sessions": sessions, "conversions": conversions,
            "conversion_rate": conversions / sessions if sessions else 0.0,
            "metric_source": METRIC_SOURCE}


def simulate(rows, settings):
    rng = np.random.default_rng(settings["seed"])
    ordered = sorted(rows, key=lambda r: (r["url"], r["captured_at"]))
    return [simulate_row(r, settings, rng) for r in ordered]
