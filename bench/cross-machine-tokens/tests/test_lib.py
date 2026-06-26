# bench/cross-machine-tokens/tests/test_lib.py
from pathlib import Path

import lib


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
