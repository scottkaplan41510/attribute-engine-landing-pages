import numpy as np

from website_attribute_finder.analyze import recovered, stats_config, timeline
from website_attribute_finder.simulate import simulate, true_rate

SETTINGS = {"seed": 1, "weeks": 12, "weekly_sessions": {"marketing": 900, "content": 300},
            "base_rate": {"marketing": 0.02, "content": 0.01}, "page_noise": 0.1,
            "planted_effects": [{"attribute": "jev_x", "value": "a", "multiplier": 2.0}]}


def rows(n=40):
    return [{"url": f"/p{i}", "captured_at": "20260101", "page_type": "marketing",
             "jev_x": "a" if i % 2 else "b", "fold_screenshot": "s.png"} for i in range(n)]


def test_same_seed_same_numbers():
    assert simulate(rows(), SETTINGS) == simulate(rows(), SETTINGS)


def test_planted_effect_applies():
    assert true_rate({"page_type": "marketing", "jev_x": "a"}, SETTINGS) == 0.04


def test_planted_effect_shows_in_output():
    out = simulate(rows(), SETTINGS)
    with_a = np.mean([r["conversion_rate"] for r in out if r["jev_x"] == "a"])
    without = np.mean([r["conversion_rate"] for r in out if r["jev_x"] == "b"])
    assert with_a > without * 1.5


def test_twelve_weeks_roll_up_to_one_row():
    row = simulate(rows(1), SETTINGS)[0]
    assert len(row["weeks"]) == 12
    assert row["sessions"] == sum(w["sessions"] for w in row["weeks"])
    assert row["metric_source"] == "simulated"


def test_simulator_never_reads_copy():
    row = {**rows(1)[0], "text": "boom"}
    plain = simulate(rows(1), SETTINGS)[0]
    with_text = simulate([row], SETTINGS)[0]
    assert plain["conversion_rate"] == with_text["conversion_rate"]


def test_vision_attributes_reach_the_engine_as_labels():
    config = {"attributes": [{"name": "hero", "computed_by": "vision", "type": "choice"}]}
    assert stats_config(config)["attributes"][0]["computed_by"] == "jev"


def test_timeline_reports_what_changed():
    config = {"attributes": [{"name": "x", "computed_by": "jev"}]}
    a = {"url": "/", "captured_at": "1", "conversion_rate": .1, "jev_x": "a", "fold_screenshot": "s"}
    b = {**a, "captured_at": "2", "jev_x": "b"}
    assert timeline([b, a], "/", config)[1]["changed"] == [{"attribute": "x", "from": "a", "to": "b"}]


def test_versions_of_a_page_differ_only_through_attributes():
    settings = {**SETTINGS, "planted_effects": []}
    a = {"url": "/", "captured_at": "1", "page_type": "marketing"}
    from website_attribute_finder.simulate import page_noise
    assert page_noise("/", settings) == page_noise("/", settings)
    assert page_noise("/", settings) != page_noise("/about", settings)


def test_broken_render_is_not_a_change():
    config = {"attributes": [{"name": "x", "computed_by": "vision"}]}
    a = {"url": "/", "captured_at": "1", "conversion_rate": .1, "jev_x": "a", "fold_screenshot": "s"}
    b = {**a, "captured_at": "2", "jev_x": "unknown"}
    assert timeline([a, b], "/", config)[1]["changed"] == []


def test_recovered_reports_found_and_missed():
    planted = [{"attribute": "jev_a", "value": "y", "multiplier": 2},
               {"attribute": "jev_b", "value": "y", "multiplier": 2}]
    cards = {"marketing": {"card": [{"attribute": "a", "value": "y", "significant": True}]}}
    assert [p["found"] for p in recovered(planted, cards)] == [True, False]


def test_cta_wordings_are_deduped():
    from website_attribute_finder.attributes import cta_labels
    assert cta_labels(["Request access", "Request access →", "About"], "request") == ["Request access"]
