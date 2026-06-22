import pytest

from anamnesis.reflect import (
    DistilledNote,
    Reflector,
    _parse_reflection,
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
