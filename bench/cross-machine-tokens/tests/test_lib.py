# bench/cross-machine-tokens/tests/test_lib.py
from pathlib import Path

import lib
import setup_synthetic


def test_scenario_has_four_notes_and_no_personal_info():
    assert len(lib.SCENARIO) == 4
    blob = " ".join(n.title + " " + n.body for n in lib.SCENARIO).lower()
    # Synthetic only: must not mention the founder's real identifiers.
    for forbidden in ("odesha", "oscar", "anamnesis-memory", "/home/"):
        assert forbidden not in blob
    projects = {n.project for n in lib.SCENARIO}
    assert projects == {"quotes-api", "global"}


def test_seed_store_writes_and_indexes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.setenv("ANAMNESIS_IMPORT_NATIVE", "0")
    count = lib.seed_store(tmp_path / "store")
    assert count == 4
    # The four markdown files exist under memory/<type>/.
    md = list((tmp_path / "store" / "memory").rglob("*.md"))
    assert len(md) == 4


def test_write_project_creates_marker_and_sources(tmp_path):
    proj = tmp_path / "quotes-api"
    written = setup_synthetic.write_project(proj)
    assert (proj / ".anamnesis" / "project").read_text().strip() == "quotes-api"
    # The seed code that the cold agent will explore exists.
    names = {p.name for p in written}
    assert "repo.ts" in names
    assert "quotes.ts" in names
    # The conventions are NOT all spelled out in the code (memory adds value).
    blob = (proj / "src" / "routes" / "quotes.ts").read_text()
    assert "POST" not in blob  # the POST route is the task, not pre-written


def test_build_warm_prompt_prepends_block():
    out = lib.build_warm_prompt("# memory\n- thing\n", task="DO IT")
    assert out.startswith("# memory")
    assert out.rstrip().endswith("DO IT")


def test_parse_usage_sums_total_input():
    u = {
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 5,
    }
    p = lib.parse_usage(u)
    assert p == {
        "input_tokens": 100,
        "output_tokens": 40,
        "cache_creation": 10,
        "cache_read": 5,
        "total_input": 115,
    }
    assert lib.parse_usage(None)["total_input"] == 0


def test_summarize_runs_averages():
    runs = [
        {"total_input": 100, "output_tokens": 10},
        {"total_input": 200, "output_tokens": 20},
    ]
    s = lib.summarize_runs("cold", runs)
    assert s["label"] == "cold"
    assert s["runs"] == 2
    assert s["avg_total_input"] == 150
    assert s["avg_output_tokens"] == 15


def test_render_chart_svg_contains_values_and_labels():
    svg = lib.render_chart_svg(cold=12000, warm=3000)
    assert svg.startswith("<svg")
    assert "</svg>" in svg
    assert "Without Anamnesis" in svg
    assert "With Anamnesis" in svg
    assert "12,000" in svg
    assert "3,000" in svg
    assert "SAMPLE" not in svg


def test_render_chart_svg_sample_watermark():
    svg = lib.render_chart_svg(cold=1, warm=1, sample=True)
    assert "SAMPLE" in svg
