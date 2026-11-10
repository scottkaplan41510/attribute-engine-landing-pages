"""Measure everything countable. No reason to pay a model to count."""

import re

VOWEL_GROUP = re.compile(r"[aeiouy]+")


def syllables(word):
    word = word.lower()
    count = len(VOWEL_GROUP.findall(word))
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def reading_grade(text):
    """Flesch-Kincaid grade level."""
    sentences = [s for s in re.split(r"[.!?\n]+", text) if s.strip()]
    words = re.findall(r"[A-Za-z']+", text)
    if not sentences or not words:
        return 0.0
    grade = (0.39 * len(words) / len(sentences)
             + 11.8 * sum(syllables(w) for w in words) / len(words) - 15.59)
    return round(grade, 1)


def cta_count(labels, pattern):
    return sum(1 for label in labels if re.search(pattern, label, re.I))


def cta_labels(labels, pattern):
    """Distinct CTA wordings, ignoring arrows, line breaks and capitalization."""
    out = {}
    for label in labels:
        clean = re.sub(r"\s+", " ", re.sub(r"[→↗]", " ", label)).strip()
        if re.search(pattern, clean, re.I):
            out.setdefault(clean.lower(), clean)
    return list(out.values())


def number_count(text):
    return len(re.findall(r"\b\d[\d,.]*[%xX+]?", text))


def measure(row, pattern):
    from attribute_engine.tag import code_attributes
    return {**code_attributes(row["text"]),
            "reading_grade": reading_grade(row["text"]),
            "cta_count": cta_count(row["clickable_labels"], pattern),
            "number_count": number_count(row["text"])}
