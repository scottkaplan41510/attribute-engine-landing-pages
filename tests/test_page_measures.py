from website_attribute_finder.capture import count_elements
from website_attribute_finder.page_measures import color_family, cta_wording
from website_attribute_finder.tokens import analyze, page_terms

CONFIG = {"cta_patterns": "get started|book a demo",
          "cta_wordings": {"get_started": "get started", "book_a_demo": "book a demo"}}
TOKENS = {"min_pages": 2, "max_share": 0.8, "top": 5}


def test_counts_skip_icons_and_inline_images():
    html = ('<img src="a.jpg"><img src="b.svg"><img src="data:x"><img src="c.png" width="16">'
            '<section></section><form></form>' + "x" * 300 + '<video></video>')
    got = count_elements(html)
    assert (got["image_count"], got["section_count"], got["form_on_page"]) == (1, 1, "yes")
    assert (got["video_count"], got["video_on_page"]) == (1, "lower")


def test_no_video():
    assert count_elements("<p>hi</p>")["video_on_page"] == "none"


def test_color_families_include_black_white_grey():
    assert color_family(255, 255, 255) == "white"
    assert color_family(10, 10, 10) == "black"
    assert color_family(128, 128, 128) == "grey"
    assert color_family(74, 155, 71) == "green"


def test_cta_wording_uses_the_first_cta():
    assert cta_wording(["Pricing", "Book a demo", "Get started"], CONFIG) == "book_a_demo"
    assert cta_wording(["Pricing"], CONFIG) == "none"


def test_terms_drop_filler_and_count_once_per_page():
    assert page_terms("the agents and the agents team", {"the", "and"}) == {
        "agents", "team", "agents agents", "agents team"}


def test_phrases_stop_at_line_breaks():
    assert "agents team" not in page_terms("agents\nteam", set())


def test_same_block_of_copy_counts_once():
    rows = [{"text": "alpha beta" if i < 3 else "gamma", "conversion_rate": 0.01 * (i + 1)} for i in range(6)]
    table = analyze(rows, {**TOKENS, "extra_stopwords": []})
    assert sum(t["term"] in ("alpha", "beta", "alpha beta") for t in table["terms"]) == 1


def test_word_table_compares_with_and_without():
    rows = [{"text": "agents win" if i < 4 else "humans lose", "conversion_rate": 0.04 + i / 1000 if i < 4 else 0.02 + i / 1000}
            for i in range(8)]
    top = {t["term"]: t for t in analyze(rows, {**TOKENS, "extra_stopwords": []})["terms"]}
    assert top["win"]["pages"] == 4
    assert top["win"]["rate_with"] > top["win"]["rate_without"]
