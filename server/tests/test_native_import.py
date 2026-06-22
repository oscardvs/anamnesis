"""Tests for importing Claude Code's native per-project memory into the store.

Claude Code keeps its own memory as markdown under
``<claude_home>/projects/<slug>/memory/<name>.md`` (front-matter: ``name``,
``description``, ``metadata.type`` in user|feedback|project|reference). Anamnesis
does not own that store, so this importer mirrors those notes into the Anamnesis
store as portable notes that then sync like any other memory.

All fixtures here are SYNTHETIC: the importer is generic transcript/markdown logic
with no hardcoded ``~/.claude`` paths and touches real data only at runtime, the
same contract as ``capture.py``. No personal data lives in this file.
"""

import json
from pathlib import Path

from anamnesis.native_import import (
    ImportResult,
    _decode_slug,
    import_native,
    map_note_type,
    parse_native_note,
    stable_id,
)
from anamnesis.store import MemoryStore


def _native(name: str, description: str, ntype: str, body: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        "metadata:\n"
        f"  type: {ntype}\n"
        "  node_type: memory\n"
        "---\n"
        f"{body}\n"
    )


def _native_project(claude_home: Path, slug: str, cwd: str | None = None) -> Path:
    """Create a native project dir with a memory/ folder and an optional transcript."""
    proj = claude_home / "projects" / slug
    (proj / "memory").mkdir(parents=True)
    if cwd is not None:
        (proj / "session.jsonl").write_text(
            json.dumps({"type": "user", "cwd": cwd}) + "\n", encoding="utf-8"
        )
    return proj


def test_parse_native_note_extracts_name_description_type_and_body():
    note = parse_native_note(
        _native("xbox-pairing", "How to pair the xbox controller", "feedback", "Hold sync 3s.")
    )
    assert note.name == "xbox-pairing"
    assert note.description == "How to pair the xbox controller"
    assert note.native_type == "feedback"
    assert note.body == "Hold sync 3s."


def test_map_note_type_feedback_is_procedural_else_semantic():
    assert map_note_type("feedback") == "procedural"
    assert map_note_type("project") == "semantic"
    assert map_note_type("reference") == "semantic"
    assert map_note_type("user") == "semantic"
    assert map_note_type("anything-unknown") == "semantic"


def test_stable_id_is_deterministic_and_ulid_shaped():
    a = stable_id("slug/name")
    b = stable_id("slug/name")
    c = stable_id("slug/other")
    assert a == b
    assert a != c
    assert len(a) == 26  # ULID canonical length


def test_import_creates_portable_notes_with_legacy_compatible_shape(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-myrepo", cwd="/home/user/myrepo")
    (proj / "memory" / "a-fact.md").write_text(
        _native("a-fact", "A durable fact", "reference", "The sky is blue."), encoding="utf-8"
    )

    result = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=lambda cwd: "myrepo"
    )

    assert isinstance(result, ImportResult)
    assert result.imported == 1
    notes = store.list()
    assert len(notes) == 1
    mem = notes[0]
    assert mem.type == "semantic"  # reference -> semantic
    assert mem.title == "A durable fact"  # native description becomes the title
    assert mem.body == "The sky is blue."
    assert mem.project == "myrepo"
    assert mem.machine_id == "m1"
    assert mem.scope == "portable"
    assert "import" in mem.tags
    assert "kind:reference" in mem.tags


def test_import_skips_the_MEMORY_index_file(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-myrepo", cwd="/home/user/myrepo")
    (proj / "memory" / "MEMORY.md").write_text("# index\n- [a](a-fact.md)\n", encoding="utf-8")
    (proj / "memory" / "a-fact.md").write_text(
        _native("a-fact", "A fact", "project", "Body."), encoding="utf-8"
    )

    result = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=lambda cwd: "myrepo"
    )

    assert result.imported == 1
    assert all("index" not in n.title.lower() for n in store.list())


def test_import_is_idempotent_no_duplicates_on_rerun(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-myrepo", cwd="/home/user/myrepo")
    (proj / "memory" / "a-fact.md").write_text(
        _native("a-fact", "A fact", "project", "Body text."), encoding="utf-8"
    )
    resolver = lambda cwd: "myrepo"  # noqa: E731

    first = import_native(store, claude_home=claude_home, machine_id="m1", resolve_project=resolver)
    second = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=resolver
    )

    assert first.imported == 1
    assert second.imported == 0
    assert second.skipped == 1
    assert len(store.list()) == 1


def test_import_dedups_against_an_existing_note_with_the_same_body(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    # A note already in the store (e.g. the earlier one-off import) with this body.
    store.write(type="semantic", title="Legacy title", body="Identical body.", project="x")
    proj = _native_project(claude_home, "-home-user-myrepo", cwd="/home/user/myrepo")
    (proj / "memory" / "dup.md").write_text(
        _native("dup", "A fact", "reference", "Identical body."), encoding="utf-8"
    )

    result = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=lambda cwd: "myrepo"
    )

    assert result.imported == 0
    assert result.skipped == 1
    assert len(store.list()) == 1  # no duplicate created


def test_import_updates_when_native_body_changed(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-myrepo", cwd="/home/user/myrepo")
    note = proj / "memory" / "a-fact.md"
    note.write_text(_native("a-fact", "A fact", "project", "Old body."), encoding="utf-8")
    resolver = lambda cwd: "myrepo"  # noqa: E731

    import_native(store, claude_home=claude_home, machine_id="m1", resolve_project=resolver)
    note.write_text(_native("a-fact", "A fact", "project", "New body."), encoding="utf-8")
    result = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=resolver
    )

    assert result.updated == 1
    bodies = {n.body for n in store.list()}
    assert bodies == {"New body."}  # same note updated in place, not duplicated


def test_import_resolves_project_from_transcript_cwd(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-ros2-ws-src", cwd="/home/user/ros2_ws/src")
    (proj / "memory" / "n.md").write_text(_native("n", "d", "project", "b"), encoding="utf-8")
    seen = {}

    def resolver(cwd: str) -> str:
        seen["cwd"] = cwd
        return "ros2_ws"

    import_native(store, claude_home=claude_home, machine_id="m1", resolve_project=resolver)

    assert seen["cwd"] == "/home/user/ros2_ws/src"
    assert store.list()[0].project == "ros2_ws"


def test_import_no_projects_dir_is_a_noop(tmp_path):
    store = MemoryStore(root=tmp_path / "store")
    result = import_native(store, claude_home=tmp_path / "nonexistent", machine_id="m1")
    assert result == ImportResult(imported=0, updated=0, skipped=0)


def test_parse_native_note_tolerates_unquoted_colons_in_frontmatter():
    # Real native notes sometimes carry unquoted colons (e.g. a "Co-Authored-By:"
    # preference), which is invalid YAML. Parsing must salvage the note, not raise.
    text = (
        "---\n"
        "name: no-coauthor\n"
        'description: Commit messages must NOT include "Co-Authored-By: Claude"\n'
        "metadata:\n"
        "  type: feedback\n"
        "---\n"
        "Body: also has a colon.\n"
    )
    note = parse_native_note(text)
    assert note.name == "no-coauthor"
    assert "Co-Authored-By" in note.description
    assert note.native_type == "feedback"
    assert note.body == "Body: also has a colon."


def test_one_malformed_note_does_not_abort_the_whole_import(tmp_path):
    claude_home = tmp_path / "claude"
    store = MemoryStore(root=tmp_path / "store")
    proj = _native_project(claude_home, "-home-user-repo", cwd="/home/user/repo")
    (proj / "memory" / "bad.md").write_text(
        "---\nname: bad\ndescription: has a: colon problem\nmetadata:\n  type: project\n---\nB1.\n",
        encoding="utf-8",
    )
    (proj / "memory" / "good.md").write_text(
        _native("good", "Fine note", "project", "B2."), encoding="utf-8"
    )

    result = import_native(
        store, claude_home=claude_home, machine_id="m1", resolve_project=lambda cwd: "repo"
    )

    # both notes salvaged, none lost to the malformed one
    assert result.imported == 2
    assert {"B1.", "B2."} <= {n.body for n in store.list()}


def test_decode_slug_reconstructs_underscored_directories(tmp_path):
    # `/home/user/ros2_ws/src` encodes to `-home-user-ros2-ws-src`; both `/` and `_`
    # become `-`, so decoding must consult the filesystem to rebuild `ros2_ws`.
    (tmp_path / "home" / "user" / "ros2_ws" / "src").mkdir(parents=True)
    decoded = _decode_slug("-home-user-ros2-ws-src", root=tmp_path)
    assert decoded == tmp_path / "home" / "user" / "ros2_ws" / "src"


def test_decode_slug_degrades_to_plain_split_for_missing_paths(tmp_path):
    decoded = _decode_slug("-home-user-myrepo", root=tmp_path)
    assert decoded == tmp_path / "home" / "user" / "myrepo"
