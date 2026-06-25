import json
import re

import pytest

from anamnesis.merge import (
    MergeGroup,
    Merger,
    _parse_merge,
    make_merger,
    resolve_min_durable,
    select_mergeable,
)
from anamnesis.store import MemoryStore

_IDS = {"a", "b", "c"}


def test_parse_merge_reads_keep_group():
    groups = _parse_merge('[{"action":"keep","keeper_id":"a","superseded_ids":["b"]}]', _IDS)
    assert groups == [MergeGroup(action="keep", superseded_ids=["b"], keeper_id="a")]


def test_parse_merge_reads_synthesize_group():
    text = (
        '[{"action":"synthesize","type":"semantic","title":"T","body":"B",'
        '"superseded_ids":["a","b"]}]'
    )
    groups = _parse_merge(text, _IDS)
    assert groups[0].action == "synthesize"
    assert groups[0].type == "semantic"
    assert groups[0].superseded_ids == ["a", "b"]


def test_parse_merge_reads_fenced_array():
    groups = _parse_merge(
        '```json\n[{"action":"keep","keeper_id":"a","superseded_ids":["b"]}]\n```', _IDS
    )
    assert groups[0].keeper_id == "a"


def test_parse_merge_empty_array():
    assert _parse_merge("[]", _IDS) == []


def test_parse_merge_rejects_nonarray():
    with pytest.raises(ValueError):
        _parse_merge('{"action":"keep"}', _IDS)


def test_parse_merge_rejects_bad_action():
    with pytest.raises(ValueError):
        _parse_merge('[{"action":"delete","superseded_ids":["a"]}]', _IDS)


def test_parse_merge_rejects_keep_missing_keeper():
    with pytest.raises(ValueError):
        _parse_merge('[{"action":"keep","superseded_ids":["a"]}]', _IDS)


def test_parse_merge_rejects_synthesize_missing_body():
    with pytest.raises(ValueError):
        _parse_merge(
            '[{"action":"synthesize","type":"semantic","title":"T","body":"",'
            '"superseded_ids":["a"]}]',
            _IDS,
        )


def test_parse_merge_rejects_bad_synthesize_type():
    with pytest.raises(ValueError):
        _parse_merge(
            '[{"action":"synthesize","type":"episodic","title":"T","body":"B",'
            '"superseded_ids":["a"]}]',
            _IDS,
        )


def test_parse_merge_rejects_empty_superseded():
    with pytest.raises(ValueError):
        _parse_merge('[{"action":"keep","keeper_id":"a","superseded_ids":[]}]', _IDS)


def test_parse_merge_rejects_hallucinated_id():
    with pytest.raises(ValueError):
        _parse_merge('[{"action":"keep","keeper_id":"a","superseded_ids":["zzz"]}]', _IDS)


def test_parse_merge_rejects_keeper_in_its_own_superseded():
    with pytest.raises(ValueError):
        _parse_merge('[{"action":"keep","keeper_id":"a","superseded_ids":["a"]}]', _IDS)


def test_parse_merge_rejects_id_reused_across_groups():
    text = (
        '[{"action":"keep","keeper_id":"a","superseded_ids":["b"]},'
        '{"action":"keep","keeper_id":"c","superseded_ids":["b"]}]'
    )
    with pytest.raises(ValueError):
        _parse_merge(text, _IDS)


def test_merger_propose_returns_groups():
    from anamnesis.store import Memory

    def client(system, user):
        return '[{"action":"keep","keeper_id":"a","superseded_ids":["b"]}]'

    notes = [
        Memory(id="a", type="semantic", title="A", body="x"),
        Memory(id="b", type="semantic", title="B", body="y"),
    ]
    merger = Merger(client=client, model_label="deepseek/test")
    groups = merger.propose(notes)
    assert groups[0].keeper_id == "a" and groups[0].superseded_ids == ["b"]


def test_merger_propose_raises_on_client_error():
    def boom(system, user):
        raise TimeoutError("down")

    merger = Merger(client=boom, model_label="deepseek/test")
    with pytest.raises(TimeoutError):
        merger.propose([])


def test_resolve_min_durable_default_and_env(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_MERGE_MIN_DURABLE", raising=False)
    assert resolve_min_durable() == 5
    monkeypatch.setenv("ANAMNESIS_MERGE_MIN_DURABLE", "9")
    assert resolve_min_durable() == 9


def test_make_merger_none_without_config(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECTION_PROVIDER", "deepseek")
    monkeypatch.delenv("ANAMNESIS_REFLECTION_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert make_merger() is None


def test_select_mergeable_filters(tmp_path):
    store = MemoryStore(root=tmp_path)
    keep = store.write(type="semantic", title="dur", body="x", project="p")
    store.write(type="episodic", title="ep", body="x", project="p", tags=["session"])
    store.write(type="semantic", title="ml", body="x", project="p", scope="machine-local")
    old = store.write(type="semantic", title="old", body="x", project="p")
    store.write(type="semantic", title="new", body="y", project="p", supersedes=[old.id])
    ids = {m.id for m in select_mergeable(store, "p")}
    assert keep.id in ids
    assert old.id not in ids  # already superseded excluded
    assert all(m.type in ("semantic", "procedural") for m in select_mergeable(store, "p"))
    assert all(m.scope == "portable" for m in select_mergeable(store, "p"))
    store.close()


def _keep_first_client(system, user):
    """A fake LLM: keep the first rendered note, supersede the rest. Reads ids from the prompt."""
    ids = re.findall(r"## \[([^\]]+)\] \[", user)
    if len(ids) < 2:
        return "[]"
    keeper, *rest = ids
    return json.dumps([{"action": "keep", "keeper_id": keeper, "superseded_ids": rest}])


def test_apply_merge_keep_sets_supersedes_and_tags(tmp_path):
    from anamnesis.merge import apply_merge

    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="A", body="same fact", project="p")
    b = store.write(type="semantic", title="B", body="same fact, reworded", project="p")
    merger = Merger(client=_keep_first_client, model_label="deepseek/test")
    result = apply_merge(store, "p", merger, machine_id="m")

    assert result.groups_applied == 1
    assert result.notes_superseded == 1
    assert result.notes_synthesized == 0
    # the keeper now supersedes the other and is tagged merged; provenance unchanged
    keeper_id = a.id if a.id != _superseded_one(store) else b.id
    keeper = store.get(keeper_id)
    assert keeper.supersedes == [_superseded_one(store)]
    assert "merged" in keeper.tags
    assert keeper.prov_source == "human"
    store.close()


def _superseded_one(store):
    return next(iter(store.superseded_ids()))


def test_apply_merge_keep_is_additive(tmp_path):
    from anamnesis.merge import apply_merge

    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="A", body="x", project="p", supersedes=["pre-existing"])
    b = store.write(type="semantic", title="B", body="y", project="p")

    def client(system, user):
        return json.dumps([{"action": "keep", "keeper_id": a.id, "superseded_ids": [b.id]}])

    apply_merge(store, "p", Merger(client=client, model_label="t"), machine_id="m")
    assert store.get(a.id).supersedes == sorted(["pre-existing", b.id])
    store.close()


def test_apply_merge_synthesize_writes_merge_note(tmp_path):
    from anamnesis.merge import apply_merge

    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="A", body="part one", project="p")
    b = store.write(type="semantic", title="B", body="part two", project="p")

    def client(system, user):
        return json.dumps(
            [
                {
                    "action": "synthesize",
                    "type": "semantic",
                    "title": "Combined",
                    "body": "part one and part two",
                    "superseded_ids": [a.id, b.id],
                }
            ]
        )

    result = apply_merge(
        store, "p", Merger(client=client, model_label="deepseek/test"), machine_id="m"
    )
    assert result.notes_synthesized == 1
    assert result.notes_superseded == 2
    synth = [m for m in store.list(project="p", type="semantic") if m.title == "Combined"]
    assert len(synth) == 1
    note = synth[0]
    assert note.prov_source == "merge"
    assert note.confidence == 0.6
    assert "merge" in note.tags
    assert sorted(note.supersedes) == sorted([a.id, b.id])
    # originals are now hidden from search but still listed
    assert {m.id for m in store.search("part", project="p")}.isdisjoint({a.id, b.id})
    assert {a.id, b.id}.issubset({m.id for m in store.list(project="p")})
    store.close()


def test_apply_groups_applies_keep_and_synthesize(tmp_path):
    from anamnesis.merge import MergeGroup, apply_groups

    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="a", body="x", project="p")
    b = store.write(type="semantic", title="b", body="y", project="p")
    c = store.write(type="semantic", title="c", body="z", project="p")

    groups = [
        MergeGroup(action="keep", keeper_id=a.id, superseded_ids=[b.id]),
        MergeGroup(
            action="synthesize",
            type="semantic",
            title="merged c",
            body="z consolidated",
            superseded_ids=[c.id],
        ),
    ]
    result = apply_groups(store, "p", groups, machine_id="m", model_label="fake/model")

    assert result.groups_applied == 2
    assert result.notes_synthesized == 1
    assert result.notes_superseded == 2
    assert store.superseded_ids() == {b.id, c.id}
    keeper = store.get(a.id)
    assert b.id in keeper.supersedes and "merged" in keeper.tags
    store.close()


def test_apply_merge_client_error_writes_nothing(tmp_path):
    from anamnesis.merge import apply_merge

    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="A", body="x", project="p")
    store.write(type="semantic", title="B", body="y", project="p")
    before = store.stats().total

    def boom(system, user):
        raise TimeoutError("down")

    with pytest.raises(TimeoutError):
        apply_merge(store, "p", Merger(client=boom, model_label="t"), machine_id="m")
    assert store.stats().total == before
    assert store.superseded_ids() == set()
    store.close()
