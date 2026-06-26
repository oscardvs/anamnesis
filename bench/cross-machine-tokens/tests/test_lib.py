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
