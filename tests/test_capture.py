from website_attribute_finder.capture import (
    first_heading, is_new_version, is_offline, normalize_path, page_type, read_copy, stored_url,
)

SITE = {"content_pattern": "^/(articles|blog)/"}


def test_normalize_path():
    assert normalize_path("https://www.example.com:80/") == "/"
    assert normalize_path("https://example.com/about/?x=1#top") == "/about"


def test_code_only_change_is_not_a_new_version():
    text = "one two three four five six seven eight nine ten " * 5
    assert not is_new_version(text, text + "eleven", 0.9)


def test_rewrite_is_a_new_version():
    assert is_new_version("alpha beta gamma delta", "one two three four", 0.9)


def test_first_capture_is_a_new_version():
    assert is_new_version(None, "anything", 0.9)


def test_page_type():
    assert page_type("/articles/x", SITE) == "content"
    assert page_type("/pricing", SITE) == "marketing"


def test_stored_url_uses_the_original_page():
    assert "/20260101id_/" in stored_url("20260101", "https://example.com/")


def test_read_copy_skips_nav_scripts_and_footer():
    raw = "<nav>Menu</nav><h1>Hello &amp; welcome</h1><script>x()</script><footer>Legal</footer>"
    assert read_copy(raw) == "Hello & welcome"


def test_outage_page_is_not_a_capture():
    assert is_offline("Temporarily Offline")
    assert is_offline("")
    assert not is_offline("<h1>Real page</h1>")


def test_first_heading():
    assert first_heading('<h1 class="x"><span>Sales</span>  <b>OS &amp; more</b></h1>') == "Sales OS & more"
    assert first_heading("<p>none</p>") == ""
