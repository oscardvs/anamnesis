import pytest

from anamnesis.migrate import apply_migration, plan_migration, rekey_front_matter
from anamnesis.store import MemoryStore


def _note(project="old", updated="2026-01-01T00:00:00+00:00", body="hello body"):
    return (
        "---\n"
        "id: 01ABC\n"
        "type: semantic\n"
        "title: A title\n"
        f"project: {project}\n"
        "machine_id: m\n"
        "scope: portable\n"
        "created_at: 2026-01-01T00:00:00+00:00\n"
        f"updated_at: {updated}\n"
        "tags: []\n"
        "---\n"
        f"{body}\n"
    )


def test_rekey_changes_only_the_project_line():
    text = _note(project="old-key")
    out = rekey_front_matter(text, "github.com/oscardvs/anamnesis")
    assert "project: github.com/oscardvs/anamnesis\n" in out
    assert "project: old-key" not in out
    assert "updated_at: 2026-01-01T00:00:00+00:00\n" in out  # preserved
    assert "id: 01ABC\n" in out
    assert out.endswith("hello body\n")
    # exactly one line differs
    diffs = sum(1 for a, b in zip(text.splitlines(), out.splitlines(), strict=True) if a != b)
    assert diffs == 1


def test_rekey_is_idempotent_when_already_target():
    text = _note(project="new-key")
    assert rekey_front_matter(text, "new-key") == text


def test_rekey_ignores_a_project_like_line_in_the_body():
    text = _note(project="old", body="project: not-frontmatter\nmore text")
    out = rekey_front_matter(text, "new")
    assert "project: new\n" in out
    assert "project: not-frontmatter" in out  # body left untouched


def test_rekey_raises_without_front_matter():
    with pytest.raises(ValueError):
        rekey_front_matter("no front matter here\n", "x")


def test_rekey_raises_without_project_field():
    text = "---\nid: 1\ntype: semantic\ntitle: t\n---\nbody\n"
    with pytest.raises(ValueError):
        rekey_front_matter(text, "x")


def _store_with(tmp_path):
    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="a", body="b", project="-slug-foo", machine_id="m")
    b = store.write(type="procedural", title="b", body="b", project="-slug-bar", machine_id="m")
    c = store.write(type="semantic", title="c", body="b", project="keep", machine_id="m")
    store.close()
    return a, b, c


def test_plan_applies_overrides_over_project_map(tmp_path):
    a, b, c = _store_with(tmp_path)
    project_map = {"-slug-foo": "foo", "-slug-bar": "bar"}
    note_overrides = {a.id: "global"}  # a is redirected to global, not foo
    by_id = {
        ch.id: ch.new_project
        for ch in plan_migration(tmp_path / "memory", project_map, note_overrides)
    }
    assert by_id[a.id] == "global"
    assert by_id[b.id] == "bar"
    assert c.id not in by_id  # "keep" has no mapping -> no change


def test_apply_rewrites_files_and_is_idempotent(tmp_path):
    a, b, c = _store_with(tmp_path)
    project_map = {"-slug-foo": "foo", "-slug-bar": "bar"}
    applied = apply_migration(tmp_path / "memory", project_map, {})
    assert len(applied) == 2
    assert apply_migration(tmp_path / "memory", project_map, {}) == []  # second run is a no-op

    store = MemoryStore(root=tmp_path)
    store.reindex()
    assert {m.title for m in store.list(project="foo")} == {"a"}
    assert {m.title for m in store.list(project="bar")} == {"b"}
    assert {m.title for m in store.list(project="keep")} == {"c"}
    store.close()


def test_apply_skips_malformed_files(tmp_path):
    a, b, c = _store_with(tmp_path)
    bad = tmp_path / "memory" / "semantic" / "bad.md"
    bad.write_text("not a note\n", encoding="utf-8")
    applied = apply_migration(tmp_path / "memory", {"-slug-foo": "foo"}, {})
    assert [ch.id for ch in applied] == [a.id]  # only the foo note changed
    assert bad.read_text(encoding="utf-8") == "not a note\n"  # untouched
