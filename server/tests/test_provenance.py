from anamnesis.provenance import _infer_source, apply_backfill, plan_backfill
from anamnesis.store import Memory, _deserialize, _serialize


def _write(dir_path, note_id, tags):
    dir_path.mkdir(parents=True, exist_ok=True)
    mem = Memory(
        id=note_id,
        type="episodic",
        title="t",
        body="body",
        tags=tags,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )  # prov_source defaults to "human"
    path = dir_path / f"{note_id}.md"
    path.write_text(_serialize(mem), encoding="utf-8")
    return path


def test_infer_source_from_tags():
    assert (
        _infer_source(Memory(id="a", type="x", title="t", body="b", tags=["import", "kind:x"]))
        == "import"
    )
    assert (
        _infer_source(
            Memory(id="a", type="x", title="t", body="b", tags=["session", "session-end"])
        )
        == "session-end"
    )
    assert _infer_source(Memory(id="a", type="x", title="t", body="b", tags=[])) == "human"


def test_plan_backfill_lists_only_changes(tmp_path):
    _write(tmp_path / "memory", "cap", ["session", "session-end"])
    _write(tmp_path / "memory", "hum", [])  # already human -> no change
    changes = plan_backfill([tmp_path / "memory"])
    assert [c.note_id for c in changes] == ["cap"]
    assert changes[0].prov_source == "session-end"


def test_apply_backfill_rewrites_frontmatter_for_memory_and_local(tmp_path):
    cap = _write(tmp_path / "memory", "cap", ["import", "kind:x"])
    loc = _write(tmp_path / "local", "loc", ["session"])
    changes = apply_backfill([tmp_path / "memory", tmp_path / "local"])
    assert {c.note_id for c in changes} == {"cap", "loc"}
    cap_mem = _deserialize(cap.read_text(encoding="utf-8"))
    loc_mem = _deserialize(loc.read_text(encoding="utf-8"))
    assert cap_mem.prov_source == "import"
    assert loc_mem.prov_source == "session-end"
    assert cap_mem.body == "body"  # body untouched
    assert cap_mem.updated_at == "2026-01-01T00:00:00+00:00"  # timestamp untouched
    # idempotent: a second pass finds nothing
    assert apply_backfill([tmp_path / "memory", tmp_path / "local"]) == []
