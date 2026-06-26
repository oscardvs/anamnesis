"""Tests for the git-as-sync backend (architecture §4 v0).

A local bare repo stands in for the Tailscale remote, so these run with no
network: write on store A, push, pull into store B, reindex, and the note is
searchable on B. That is the Amsterdam round-trip, made hermetic.
"""

import subprocess
from pathlib import Path

from anamnesis.store import MemoryStore
from anamnesis.sync import GitSyncBackend


def _bare_remote(path: Path) -> str:
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(path)], check=True, capture_output=True
    )
    return str(path)


def _backend(store: MemoryStore, remote: str, machine_id: str) -> GitSyncBackend:
    backend = GitSyncBackend(store.memory_dir, remote=remote, machine_id=machine_id)
    backend.init()
    return backend


def test_round_trip_write_on_A_appears_on_B(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")

    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = _backend(store_a, remote, "desktop")
    note = store_a.write(
        type="procedural",
        title="Amsterdam scenario",
        body="memory written on the desktop appears on the laptop",
        project="anamnesis",
    )
    res_a = backend_a.sync()
    assert res_a.pushed

    store_b = MemoryStore(root=tmp_path / "B")
    backend_b = _backend(store_b, remote, "laptop")
    backend_b.sync()  # pulls A's commit into B's memory/

    assert store_b.reindex() == 1
    assert [m.id for m in store_b.search("Amsterdam")] == [note.id]
    assert store_b.get(note.id).body == "memory written on the desktop appears on the laptop"


def test_index_db_is_never_tracked(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = _backend(store_a, remote, "desktop")
    store_a.write(type="semantic", title="t", body="b", project="p")
    backend_a.sync()

    tracked = subprocess.run(
        ["git", "-C", str(store_a.memory_dir), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".db" not in tracked


def test_conflicting_edit_is_surfaced_not_silently_dropped(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = _backend(store_a, remote, "desktop")
    note = store_a.write(type="semantic", title="shared", body="A version", project="p")
    backend_a.sync()

    store_b = MemoryStore(root=tmp_path / "B")
    backend_b = _backend(store_b, remote, "laptop")
    backend_b.sync()  # B now has the note too

    # Both machines edit the SAME note file divergently.
    rel = f"{note.type}/{note.id}.md"
    path_a = store_a.memory_dir / rel
    path_b = store_b.memory_dir / rel
    path_a.write_text(path_a.read_text().replace("A version", "desktop edit"))
    path_b.write_text(path_b.read_text().replace("A version", "laptop edit"))

    assert backend_a.sync().pushed  # desktop edit reaches the remote first
    res_b = backend_b.sync()  # laptop edit now conflicts on rebase

    assert res_b.conflicted
    assert "laptop edit" in path_b.read_text()  # local edit preserved, not silently dropped


def test_durability_over_many_sync_cycles(tmp_path):
    # Advance-threshold: memory round-trips across >=20 consecutive sync cycles
    # with the index rebuilt each time and no corruption / divergence.
    remote = _bare_remote(tmp_path / "remote.git")
    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = _backend(store_a, remote, "desktop")
    store_b = MemoryStore(root=tmp_path / "B")
    backend_b = _backend(store_b, remote, "laptop")

    cycles = 24
    for i in range(cycles):
        store_a.write(type="semantic", title=f"note-{i}", body=f"durable body {i}", project="p")
        backend_a.sync()  # push
        backend_b.sync()  # pull
        store_b.reindex()
        assert store_b.search(f"note-{i}"), f"cycle {i}: newest note not visible on B"

    store_b.reindex()
    assert store_b.stats().total == cycles  # every note converged onto B
    assert store_a.stats().total == cycles  # A's own index intact
    assert store_b.get(store_a.list()[-1].id).body == "durable body 0"  # files uncorrupted


def test_state_reports_remote_and_head(tmp_path):
    remote = _bare_remote(tmp_path / "remote.git")
    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = _backend(store_a, remote, "desktop")
    store_a.write(type="semantic", title="t", body="b", project="p")
    backend_a.sync()

    st = backend_a.state()
    assert st.initialized is True
    assert st.remote == remote
    assert st.head  # a commit sha
    assert st.dirty is False


def test_commit_local_commits_dirty_tree_and_inits_non_repo(tmp_path):
    store = MemoryStore(root=tmp_path / "A")
    store.write(type="semantic", title="t", body="b", project="p")
    backend = GitSyncBackend(store.memory_dir, remote=None, machine_id="m")

    assert not (store.memory_dir / ".git").exists()  # not a repo yet
    assert backend.commit_local() is True  # inits, then commits the markdown
    assert (store.memory_dir / ".git").is_dir()

    porcelain = subprocess.run(
        ["git", "-C", str(store.memory_dir), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert porcelain.strip() == ""  # working tree clean after commit
    assert backend.state().head  # a commit sha exists


def test_commit_local_noop_on_clean_tree(tmp_path):
    store = MemoryStore(root=tmp_path / "A")
    store.write(type="semantic", title="t", body="b", project="p")
    backend = GitSyncBackend(store.memory_dir, remote=None, machine_id="m")

    assert backend.commit_local() is True  # first commit
    head1 = backend.state().head
    assert backend.commit_local() is False  # nothing new to commit
    assert backend.state().head == head1  # HEAD unchanged


def test_sync_no_remote_reports_committed_via_commit_local(tmp_path):
    store = MemoryStore(root=tmp_path / "A")
    store.write(type="semantic", title="t", body="b", project="p")
    backend = GitSyncBackend(store.memory_dir, remote=None, machine_id="m")

    res = backend.sync()
    assert res.detail.startswith("committed locally")
    assert backend.sync().detail.startswith("nothing to commit")  # second sync, clean tree
