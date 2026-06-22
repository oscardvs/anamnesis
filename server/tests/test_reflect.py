import pytest

from anamnesis.reflect import (
    DistilledNote,
    Reflector,
    _parse_reflection,
    apply_reflection,
    make_reflector,
    resolve_min_episodics,
    select_unreflected,
)
from anamnesis.store import MemoryStore


def _client_returning(text):
    def call(system, user):
        return text

    return call


def test_parse_reflection_reads_array():
    notes = _parse_reflection('[{"type": "semantic", "title": "T", "body": "B"}]')
    assert notes == [DistilledNote(type="semantic", title="T", body="B")]


def test_parse_reflection_reads_fenced_array():
    notes = _parse_reflection('```json\n[{"type": "procedural", "title": "T", "body": "B"}]\n```')
    assert notes[0].type == "procedural"


def test_parse_reflection_empty_array():
    assert _parse_reflection("[]") == []


def test_parse_reflection_rejects_bad_type():
    with pytest.raises(ValueError):
        _parse_reflection('[{"type": "episodic", "title": "T", "body": "B"}]')


def test_parse_reflection_rejects_missing_body():
    with pytest.raises(ValueError):
        _parse_reflection('[{"type": "semantic", "title": "T", "body": ""}]')


def test_parse_reflection_rejects_nonarray():
    with pytest.raises(ValueError):
        _parse_reflection('{"type": "semantic"}')


def test_select_unreflected_excludes_reflected(tmp_path):
    store = MemoryStore(root=tmp_path)
    a = store.write(type="episodic", title="a", body="x", project="p", tags=["session"])
    store.write(type="episodic", title="b", body="y", project="p", tags=["session", "reflected"])
    store.write(type="semantic", title="c", body="z", project="p")  # not episodic
    out = select_unreflected(store, "p")
    assert [m.id for m in out] == [a.id]
    store.close()


def test_reflector_returns_distilled_notes():
    reflector = Reflector(
        client=_client_returning(
            '[{"type":"semantic","title":"Prefers uv","body":"Use uv for envs."},'
            '{"type":"procedural","title":"Run tests","body":"uv run pytest."}]'
        ),
        model_label="deepseek/test",
    )
    notes = reflector.reflect([])
    assert [n.type for n in notes] == ["semantic", "procedural"]
    assert notes[0].title == "Prefers uv"


def test_reflector_raises_on_client_error():
    def boom(system, user):
        raise TimeoutError("down")

    reflector = Reflector(client=boom, model_label="deepseek/test")
    with pytest.raises(TimeoutError):
        reflector.reflect([])


def test_resolve_min_episodics_default_and_env(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_REFLECT_MIN_EPISODICS", raising=False)
    assert resolve_min_episodics() == 5
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "12")
    assert resolve_min_episodics() == 12


def test_make_reflector_none_without_config(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECTION_PROVIDER", "deepseek")
    monkeypatch.delenv("ANAMNESIS_REFLECTION_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert make_reflector() is None


def test_apply_reflection_writes_notes_and_tags_episodics(tmp_path):
    store = MemoryStore(root=tmp_path)
    eps = [
        store.write(type="episodic", title=f"s{i}", body="did work", project="p", tags=["session"])
        for i in range(3)
    ]
    reflector = Reflector(
        client=_client_returning(
            '[{"type":"semantic","title":"Prefers uv","body":"Use uv."},'
            '{"type":"procedural","title":"Tests","body":"uv run pytest."}]'
        ),
        model_label="deepseek/test",
    )
    result = apply_reflection(store, "p", reflector, machine_id="m")
    assert result.episodics == 3
    assert result.notes_written == 2

    reflections = store.list(project="p", type="semantic") + store.list(
        project="p", type="procedural"
    )
    assert len(reflections) == 2
    note = reflections[0]
    assert note.prov_source == "reflection"
    assert note.prov_model == "deepseek/test"
    assert note.confidence == 0.6
    assert "reflection" in note.tags

    # episodics are now tagged reflected, so a second run distills nothing
    for ep in eps:
        assert "reflected" in store.get(ep.id).tags
    assert select_unreflected(store, "p") == []
    store.close()


def test_apply_reflection_writes_nothing_on_client_error(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="episodic", title="s", body="x", project="p", tags=["session"])

    def boom(system, user):
        raise TimeoutError("down")

    reflector = Reflector(client=boom, model_label="deepseek/test")
    with pytest.raises(TimeoutError):
        apply_reflection(store, "p", reflector, machine_id="m")
    assert store.list(project="p", type="semantic") == []
    assert select_unreflected(store, "p") != []  # episodics untouched
    store.close()


def test_select_unreflected_excludes_machine_local(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(
        type="episodic", title="ml", body="x", project="p", tags=["session"], scope="machine-local"
    )
    assert select_unreflected(store, "p") == []
    store.close()


def test_parse_reflection_rejects_missing_title():
    with pytest.raises(ValueError):
        _parse_reflection('[{"type": "semantic", "title": "", "body": "B"}]')
