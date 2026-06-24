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
