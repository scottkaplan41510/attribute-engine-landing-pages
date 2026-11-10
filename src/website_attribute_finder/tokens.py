"""Which real words and phrases go with a higher rate. Counting and code only."""

import re
from collections import Counter

import numpy as np
from scipy import stats

from attribute_engine.stats import ALPHA, METRIC, benjamini_hochberg

# Single words and two-word phrases, filler removed, each compared against the metric.
STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been
before being below between both but by can can't cannot could couldn't did didn't do does
doesn't doing don't down during each even ever every few for from further get gets getting
got had hasn't has have haven't having he her here hers herself him himself his how however
i if in into is isn't it it's its itself just let like likely made make makes many may me
might more most much must my myself need needs no nor not now of off often on once one only
or other our ours ourselves out over own per rather really same see she should shouldn't so
some such than that that's the their theirs them themselves then there there's these they
this those through to too under until up upon us use used uses using very via want was
wasn't way ways we well were weren't what when where whether which while who whom why will
with within without won't would wouldn't yet you your yours yourself yourselves
new two three first next back still take across
""".split())
WORD = re.compile(r"[a-z][a-z'\-]+")


def page_terms(text, stopwords):
    """Each term once per page. A word repeated on one page should not count as many."""
    found = set()
    for line in text.lower().splitlines():  # a phrase never runs across two lines
        words = [w for w in WORD.findall(line) if w not in stopwords and len(w) > 2]
        found |= set(words) | {f"{a} {b}" for a, b in zip(words, words[1:])}
    return found


def analyze(rows, settings):
    """Rate with each term vs without it. Each term is a test, so all are adjusted together."""
    stop = STOPWORDS | set(settings.get("extra_stopwords", []))
    terms = [page_terms(r["text"], stop) for r in rows]
    counts = Counter(t for page in terms for t in page)
    floor, ceiling = settings["min_pages"], min(settings["max_share"] * len(rows),
                                                len(rows) - settings["min_pages"])
    y = np.array([float(r[METRIC]) for r in rows])
    found, seen = [], set()
    for term, n in sorted(counts.items(), key=lambda c: (len(c[0]), c[0])):
        if not floor <= n <= ceiling:
            continue
        has = np.array([term in page for page in terms])
        # Phrases on exactly the same pages are one block of copy, so keep the shortest.
        if has.tobytes() in seen:
            continue
        seen.add(has.tobytes())
        p = float(stats.ttest_ind(y[has], y[~has], equal_var=False).pvalue)
        found.append({"term": term, "pages": n, "rate_with": float(y[has].mean()),
                      "rate_without": float(y[~has].mean()), "p_value": p,
                      "correlation": float(stats.pearsonr(has.astype(float), y)[0])})
    if not found:
        return {"tested": 0, "significant": 0, "terms": []}
    for row, adjusted in zip(found, benjamini_hochberg([r["p_value"] for r in found])):
        row["p_adjusted"], row["significant"] = float(adjusted), bool(adjusted < ALPHA)
    found.sort(key=lambda r: (-abs(r["rate_with"] - r["rate_without"]), r["term"]))
    return {"tested": len(found), "significant": sum(r["significant"] for r in found),
            "terms": found[:settings["top"]]}
