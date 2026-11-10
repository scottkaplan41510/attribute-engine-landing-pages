import json
import shutil
from pathlib import Path

from website_attribute_finder import example

ROOT = Path(__file__).resolve().parents[1]


def test_illustrative_sample_builds_offline_and_finds_what_was_planted(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config" / "example", tmp_path / "config" / "example")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    example.build("example", web=tmp_path / "web")
    result = json.loads((tmp_path / "web" / "src" / "data" / "results.json").read_text())
    assert result["sample"] and result["banner"] == "Illustrative data. Not real analytics."
    assert len(result["pages"]) == 16
    assert all(p["url"].startswith("https://www.example.com") for p in result["pages"])
    card = result["scorecards"]["page"]["card"]
    found = {(r["attribute"], r["value"]) for r in card if r["significant"]}
    assert ("proof_type", "customer_quote") in found
    assert (tmp_path / "web" / "public" / "shots" / "p1-fold.jpg").exists()
