"""Reflection / distillation pass (architecture section 6). Reads a project's
un-reflected episodic notes and distills durable semantic/procedural notes via the
swappable LLM (reusing the B1 client/config). Provenance is recorded as
``prov_source=reflection`` with a low confidence so the output is reviewable
(architecture section 9). There is no fallback: a failed or invalid LLM response
aborts the project rather than fabricating a note.

Generic logic; tests inject a fake client and never touch the network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from anamnesis.llm_summarizer import (
    LLMClient,
    _http_client,
    _strip_fences,
    _window,
    resolve_reflection_config,
)
from anamnesis.redact import redact
from anamnesis.store import Memory, MemoryStore

_DEFAULT_MAX_CHARS = 480_000
_DEFAULT_CONFIDENCE = 0.6

REFLECT_SYSTEM_PROMPT = (
    "You distill a developer's past session notes for one project into durable, "
    "reusable memory. You are given several episodic notes, each a summary of one "
    "Claude Code session.\n\n"
    "Return ONLY a JSON array, no prose. Each element is an object:\n"
    '{"type": "semantic" | "procedural", "title": <string>, "body": <string>}\n\n'
    "Use 'semantic' for durable facts, decisions, and preferences; use 'procedural' "
    "for repeatable how-tos and procedures. Merge points that recur across sessions "
    "into one entry. Omit one-off chatter, transient state, and anything specific to a "
    "single session. Keep each entry concise. Return an empty array [] if nothing is "
    "worth keeping. Never include secrets, API keys, tokens, or credentials."
)


@dataclass
class DistilledNote:
    """One durable note the reflector proposes."""

    type: str  # "semantic" | "procedural"
    title: str
    body: str


def select_unreflected(store: MemoryStore, project: str) -> list[Memory]:
    """A project's portable episodic notes that have not yet been reflected."""
    return [
        m
        for m in store.list(project=project, type="episodic", scope="portable")
        if "reflected" not in m.tags
    ]


def _render_episodics(episodics: list[Memory]) -> str:
    return "\n\n".join(f"## {m.title}\n{m.body}" for m in episodics)


def _parse_reflection(text: str) -> list[DistilledNote]:
    """Parse the model's JSON array of distilled notes. Raises ValueError on a bad shape."""
    data = json.loads(_strip_fences(text))
    if not isinstance(data, list):
        raise ValueError("reflection output is not a JSON array")
    notes: list[DistilledNote] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("reflection item is not an object")
        ntype = str(item.get("type", "")).strip()
        title = str(item.get("title", "")).strip()
        body = str(item.get("body", "")).strip()
        if ntype not in ("semantic", "procedural"):
            raise ValueError(f"invalid reflection type: {ntype!r}")
        if not (title and body):
            raise ValueError("reflection item missing title or body")
        notes.append(DistilledNote(type=ntype, title=title, body=body))
    return notes


@dataclass
class Reflector:
    """Distill episodic notes into durable notes via an injected LLM client."""

    client: LLMClient
    model_label: str
    max_chars: int = _DEFAULT_MAX_CHARS

    def reflect(self, episodics: list[Memory]) -> list[DistilledNote]:
        content = _window(redact(_render_episodics(episodics)), self.max_chars)
        text = self.client(REFLECT_SYSTEM_PROMPT, content)
        return _parse_reflection(text)


@dataclass
class ReflectResult:
    """Outcome of reflecting one project."""

    project: str
    episodics: int
    notes_written: int


def resolve_min_episodics() -> int:
    """Min un-reflected episodics before a project is worth reflecting (env-overridable)."""
    try:
        return int(os.environ.get("ANAMNESIS_REFLECT_MIN_EPISODICS", "5"))
    except ValueError:
        return 5


def make_reflector() -> Reflector | None:
    """Build a Reflector from config, or None when no provider/model/key is configured."""
    cfg = resolve_reflection_config()
    if not (cfg.model and cfg.base_url and cfg.api_key):
        return None
    client = _http_client(cfg.base_url, cfg.api_key, cfg.model, cfg.timeout)
    return Reflector(
        client=client,
        model_label=f"{cfg.provider}/{cfg.model}",
        max_chars=cfg.max_tokens * 4,
    )


def apply_reflection(
    store: MemoryStore,
    project: str,
    reflector: Reflector,
    *,
    machine_id: str,
    confidence: float = _DEFAULT_CONFIDENCE,
) -> ReflectResult:
    """Distill a project's un-reflected episodics, write the notes, tag the sources.

    The LLM call happens first; if it raises, nothing is written (no fallback).
    """
    episodics = select_unreflected(store, project)
    notes = reflector.reflect(episodics)
    for note in notes:
        store.write(
            type=note.type,
            title=note.title,
            body=note.body,
            project=project,
            machine_id=machine_id,
            scope="portable",
            tags=["reflection"],
            prov_source="reflection",
            prov_model=reflector.model_label,
            confidence=confidence,
        )
    for ep in episodics:
        ep.tags = sorted(set(ep.tags) | {"reflected"})
        store.put(ep)
    return ReflectResult(project=project, episodics=len(episodics), notes_written=len(notes))
