import pytest

from website_attribute_finder import live, safety
from website_attribute_finder.analyze import stats_config
from website_attribute_finder.page_measures import contrast, sentiment_score


def urls(n):
    return "\n".join(f"https://example.com/{i},{i}.5%" for i in range(n))


def test_rates_read_either_way():
    assert live.parse_rate("12.5%") == 0.125
    assert live.parse_rate("0.125") == 0.125


def test_any_metric_name_and_column_order():
    rows, metric = live.parse_rows("revenue,url\n" + "\n".join(f"10,https://e.com/{i}" for i in range(4)))
    assert metric == "revenue" and rows[0] == {"url": "https://e.com/0", "conversion_rate": 10.0}


def test_duplicate_urls_count_once():
    with pytest.raises(live.BadInput, match="This has 1"):
        live.parse_rows("url,rate\nhttps://e.com/,1\nhttps://e.com/,2")


def test_page_cap():
    with pytest.raises(live.BadInput):
        live.parse_rows("url,rate\n" + urls(live.MAX_PAGES + 1))


def test_needs_two_columns():
    with pytest.raises(live.BadInput):
        live.parse_rows("url,a,b\nhttps://e.com,1,2")


def test_private_addresses_are_refused(monkeypatch):
    for bad in ("http://127.0.0.1/", "http://169.254.169.254/latest", "http://localhost/",
                "file:///etc/passwd", "http://user:pass@example.com/"):
        with pytest.raises(safety.UnsafeUrl):
            safety.check_url(bad)


def test_custom_attribute_needs_options():
    with pytest.raises(live.BadInput):
        live.clean_custom({"name": "x", "question": "y", "type": "choice", "options": {"a": "1"}})


def test_custom_yes_no():
    got = live.clean_custom({"name": "Mentions Price!", "question": "Mentions price?", "type": "boolean"})
    assert (got["name"], got["computed_by"]) == ("mentions_price", "jev")


def test_sentiment_runs_as_a_number():
    config = {"attributes": [{"name": "sentiment", "computed_by": "jev", "score_as_number": True}]}
    assert stats_config(config)["attributes"][0]["computed_by"] == "code"
    assert sentiment_score({"positive": 0.7, "negative": 0.2, "neutral": 0.1}) == 0.5


def test_contrast_ends():
    assert contrast((255, 255, 255), (0, 0, 0)) == 21.0
    assert contrast((10, 20, 30), (10, 20, 30)) == 1.0


def test_server_refuses_private_urls_before_spending_a_run(monkeypatch):
    from fastapi.testclient import TestClient
    from website_attribute_finder import run_store, server
    monkeypatch.setattr(run_store, "take_daily_slot", lambda limit: pytest.fail("slot used"))
    server.app.dependency_overrides[server.require_token] = lambda: None
    csv = "url,rate\nhttp://127.0.0.1/,1\nhttp://localhost/,2\nhttp://10.0.0.1/,3\nhttp://169.254.169.254/,4\n"
    response = TestClient(server.app).post("/run", json={"csv": csv})
    server.app.dependency_overrides.clear()
    assert response.status_code == 422 and "public" in response.json()["detail"]


def test_nothing_kept_when_keep_runs_is_off(monkeypatch):
    import io

    from PIL import Image

    from website_attribute_finder import run_store, server
    monkeypatch.setattr(server, "KEEP_RUNS", False)
    monkeypatch.setattr(run_store, "put", lambda *a: pytest.fail("nothing should be saved"))
    buffer = io.BytesIO()
    Image.new("RGB", (1440, 900), "white").save(buffer, "JPEG")
    fold = server.store_shot("r" * 32, "p1-fold.jpg", buffer.getvalue())
    assert fold.startswith("data:image/jpeg;base64,")
    assert server.store_shot("r" * 32, "p1-full.jpg", buffer.getvalue()) is None


def test_catalog_is_public():
    from fastapi.testclient import TestClient

    from website_attribute_finder import server
    body = TestClient(server.app).get("/catalog").json()
    assert body["attributes"] and body["min_pages"] == live.MIN_PAGES
