"""Tests for content-hash de-duplication.

Imports and multi-machine captures can produce byte-identical notes (empty
session summaries, the same fact written on several machines). De-dup collapses
each group of identical bodies to one keeper. Synthetic fixtures only.
"""

from anamnesis.dedup import apply_dedup, plan_dedup
from anamnesis.store import MemoryStore


def test_plan_dedup_prefers_a_global_keeper(tmp_path):
    store = MemoryStore(root=tmp_path)
    g = store.write(
        type="semantic", title="pref", body="same body", project="global", machine_id="m"
    )
    p = store.write(type="semantic", title="pref", body="same body", project="p", machine_id="m")
    store.write(type="semantic", title="unique", body="different body", project="p", machine_id="m")

    changes = plan_dedup(store.memory_dir)

    assert len(changes) == 1
    assert changes[0].kept_id == g.id  # global copy kept
    assert changes[0].removed_id == p.id


def test_plan_dedup_ignores_unique_notes(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="a", body="one", project="p", machine_id="m")
    store.write(type="semantic", title="b", body="two", project="p", machine_id="m")
    assert plan_dedup(store.memory_dir) == []


def test_apply_dedup_keeps_one_and_removes_the_rest(tmp_path):
    store = MemoryStore(root=tmp_path)
    a = store.write(type="episodic", title="s", body="dup", project="x", machine_id="m")
    b = store.write(type="episodic", title="s", body="dup", project="y", machine_id="m")

    changes = apply_dedup(store.memory_dir)

    assert len(changes) == 1
    assert store.reindex() == 1  # exactly one survivor on disk
    survivors = {m.id for m in store.list()}
    assert survivors == {min(a.id, b.id)}  # keeper = earliest/lowest id (created_at ties)


def test_apply_dedup_does_not_touch_the_local_tree(tmp_path):
    # De-dup operates on the synced memory/ tree; machine-local notes are separate.
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="s", body="dup", project="x", machine_id="m")
    store.write(type="semantic", title="s", body="dup", project="y", machine_id="m")
    loc = store.write(
        type="semantic", title="s", body="dup", project="z", machine_id="m", scope="machine-local"
    )

    apply_dedup(store.memory_dir)
    store.reindex()

    # the machine-local note is untouched (still its own note, in the local tree)
    assert store.get(loc.id).scope == "machine-local"
