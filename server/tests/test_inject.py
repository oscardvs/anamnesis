import subprocess

from anamnesis.inject import (
    _normalize_remote,
    render_inject,
    resolve_project_key,
    select_inject,
)
from anamnesis.store import Memory, MemoryStore


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_normalize_remote_scp_and_https_and_path():
    assert (
        _normalize_remote("git@github.com:oscardvs/anamnesis.git")
        == "github.com/oscardvs/anamnesis"
    )
    assert (
        _normalize_remote("https://github.com/oscardvs/Anamnesis.git")
        == "github.com/oscardvs/anamnesis"
    )
    assert _normalize_remote("/home/odesha/anamnesis-memory.git") == "/home/odesha/anamnesis-memory"


def test_resolve_project_key_prefers_git_remote(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:oscardvs/anamnesis.git")
    assert resolve_project_key(tmp_path) == "github.com/oscardvs/anamnesis"


def test_resolve_project_key_falls_back_to_repo_dirname(tmp_path):
    repo = tmp_path / "MyRepo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    assert resolve_project_key(repo) == "myrepo"


def test_resolve_project_key_non_git_uses_cwd_basename(tmp_path):
    d = tmp_path / "PlainDir"
    d.mkdir()
    assert resolve_project_key(d) == "plaindir"


def _write(store, **kw):
    kw.setdefault("machine_id", "m")
    return store.write(**kw)


def test_select_inject_always_includes_global(tmp_path):
    store = MemoryStore(root=tmp_path)
    _write(store, type="semantic", title="pref", body="no em dashes", project="global")
    _write(store, type="semantic", title="other", body="x", project="someproj")
    titles = {m.title for m in select_inject(store, project="unrelated", k=8)}
    assert "pref" in titles  # global always present
    assert "other" not in titles  # other project excluded


def test_select_inject_scopes_durable_and_reserves_recent_episodic(tmp_path):
    store = MemoryStore(root=tmp_path)
    for i in range(10):
        _write(store, type="procedural", title=f"proc{i}", body="b", project="p")
    e1 = _write(store, type="episodic", title="old-session", body="b", project="p")
    e2 = _write(store, type="episodic", title="new-session", body="b", project="p")
    sel = select_inject(store, project="p", k=8)
    titles = [m.title for m in sel]
    assert len(sel) == 8  # capped at k (no global notes here)
    # up to two most-recent episodic reserved for continuity
    assert "new-session" in titles
    assert e2.id in {m.id for m in sel} and e1.id in {m.id for m in sel}
    # the rest are durable procedural notes
    assert sum(1 for m in sel if m.type == "procedural") == 6


def test_render_inject_includes_title_body_and_provenance(tmp_path):
    store = MemoryStore(root=tmp_path)
    _write(store, type="procedural", title="WAL mode", body="set busy_timeout", project="p")
    text = render_inject(select_inject(store, project="p", k=8))
    assert "WAL mode" in text
    assert "set busy_timeout" in text
    assert "project: p" in text  # provenance line


def test_render_inject_empty_is_blank(tmp_path):
    store = MemoryStore(root=tmp_path)
    assert render_inject(select_inject(store, project="p", k=8)) == ""


def test_resolve_project_key_marker_in_cwd_wins(tmp_path):
    (tmp_path / ".anamnesis").mkdir()
    (tmp_path / ".anamnesis" / "project").write_text("pinned-key\n", encoding="utf-8")
    assert resolve_project_key(tmp_path) == "pinned-key"


def test_resolve_project_key_marker_found_up_tree(tmp_path):
    (tmp_path / ".anamnesis").mkdir()
    (tmp_path / ".anamnesis" / "project").write_text("ros2_ws\n", encoding="utf-8")
    sub = tmp_path / "src" / "pkg"
    sub.mkdir(parents=True)
    assert resolve_project_key(sub) == "ros2_ws"


def test_resolve_project_key_marker_beats_git_remote(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:oscardvs/anamnesis.git")
    (tmp_path / ".anamnesis").mkdir()
    (tmp_path / ".anamnesis" / "project").write_text("pinned-key\n", encoding="utf-8")
    assert resolve_project_key(tmp_path) == "pinned-key"


def test_resolve_project_key_blank_marker_falls_through(tmp_path):
    d = tmp_path / "PlainDir"
    (d / ".anamnesis").mkdir(parents=True)
    (d / ".anamnesis" / "project").write_text("   \n\n", encoding="utf-8")
    assert resolve_project_key(d) == "plaindir"  # blank marker ignored -> basename


def test_resolve_project_key_marker_not_read_at_or_above_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True)
    (home / ".anamnesis").mkdir()
    (home / ".anamnesis" / "project").write_text("home-level\n", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    assert resolve_project_key(proj) == "proj"  # home marker not picked up


def test_select_inject_excludes_superseded(tmp_path):
    store = MemoryStore(root=tmp_path)
    old = _write(store, type="semantic", title="old-fact", body="x", project="p")
    _write(store, type="semantic", title="new-fact", body="y", project="p", supersedes=old.id)
    g_old = _write(store, type="semantic", title="g-old", body="x", project="global")
    _write(store, type="semantic", title="g-new", body="y", project="global", supersedes=g_old.id)
    ids = {m.id for m in select_inject(store, project="p", k=8)}
    assert old.id not in ids  # superseded project note hidden
    assert g_old.id not in ids  # superseded global note hidden


def test_select_inject_drops_reflected_episodics(tmp_path):
    store = MemoryStore(root=tmp_path)
    _write(store, type="episodic", title="kept-session", body="b", project="p", tags=["session"])
    _write(
        store,
        type="episodic",
        title="done-session",
        body="b",
        project="p",
        tags=["session", "reflected"],
    )
    titles = {m.title for m in select_inject(store, project="p", k=8)}
    assert "kept-session" in titles
    assert "done-session" not in titles  # already distilled


def test_select_inject_confidence_breaks_updated_at_tie(tmp_path):
    store = MemoryStore(root=tmp_path)
    ts = "2026-01-01T00:00:00+00:00"
    store.put(
        Memory(
            id="lo",
            type="semantic",
            title="lo",
            body="x",
            project="p",
            confidence=0.6,
            created_at=ts,
            updated_at=ts,
        )
    )
    store.put(
        Memory(
            id="hi",
            type="semantic",
            title="hi",
            body="x",
            project="p",
            confidence=1.0,
            created_at=ts,
            updated_at=ts,
        )
    )
    sel = select_inject(store, project="p", k=8)
    assert sel[0].id == "hi"  # equal updated_at -> higher confidence first


def test_render_inject_labels_reflection_provenance(tmp_path):
    store = MemoryStore(root=tmp_path)
    _write(
        store,
        type="semantic",
        title="distilled",
        body="durable fact",
        project="p",
        prov_source="reflection",
        confidence=0.6,
    )
    text = render_inject(select_inject(store, project="p", k=8))
    assert "source: reflection (confidence 0.6)" in text


def test_render_inject_no_source_label_for_human_note(tmp_path):
    store = MemoryStore(root=tmp_path)
    _write(store, type="semantic", title="human-fact", body="x", project="p")
    text = render_inject(select_inject(store, project="p", k=8))
    assert "source:" not in text
