import pytest

from anamnesis.migrate import rekey_front_matter


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
