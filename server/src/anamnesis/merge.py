"""Supersession / merge pass (slice B). Consolidates a project's redundant DURABLE
notes by SETTING ``supersedes`` via the swappable LLM (reusing the reflection
client/config). The model proposes merge groups; each group either KEEPS one
existing note (the rest become superseded) or SYNTHESIZES a new consolidated note
(all originals superseded). Synthesized notes are recorded as ``prov_source=merge``
with a low confidence so they stay reviewable (architecture section 9). There is no
fallback: a failed, invalid, or id-hallucinating response aborts the project and
writes nothing.

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
from anamnesis.store import Memory, MemoryStore, _utcnow

_DEFAULT_MAX_CHARS = 480_000
_DEFAULT_CONFIDENCE = 0.6
_DURABLE = ("procedural", "semantic")

MERGE_SYSTEM_PROMPT = (
    "You consolidate a developer's durable memory notes for one project. You are given "
    "several notes, each with its id, type, title, and body.\n\n"
    "Return ONLY a JSON array, no prose. Find groups of REDUNDANT notes (notes that "
    "state the same information, possibly in different words). For each group of 2 or "
    "more redundant notes, return one object:\n"
    '{"action": "keep", "keeper_id": <id>, "superseded_ids": [<id>, ...]}\n'
    '{"action": "synthesize", "type": "semantic" | "procedural", "title": <string>, '
    '"body": <string>, "superseded_ids": [<id>, ...]}\n\n'
    "Use 'keep' when one existing note already says everything the group says: put that "
    "note's id in keeper_id and EVERY OTHER note's id in superseded_ids. Use 'synthesize' "
    "when the notes are complementary and should be combined into one better note: write "
    "the new type/title/body and put ALL the originals' ids in superseded_ids. Leave "
    "genuinely distinct notes alone (do not force unrelated notes together). Return an "
    "empty array [] if nothing should be merged. Use only the ids given to you. Never "
    "include secrets, API keys, tokens, or credentials."
)


@dataclass
class MergeGroup:
    """One validated merge proposal: keep an existing note or synthesize a new one."""

    action: str  # "keep" | "synthesize"
    superseded_ids: list[str]
    keeper_id: str = ""  # for "keep"
    type: str = ""  # for "synthesize"
    title: str = ""  # for "synthesize"
    body: str = ""  # for "synthesize"


def resolve_min_durable() -> int:
    """Min durable notes before a project is worth a merge call (env-overridable)."""
    try:
        return int(os.environ.get("ANAMNESIS_MERGE_MIN_DURABLE", "5"))
    except ValueError:
        return 5


def select_mergeable(store: MemoryStore, project: str) -> list[Memory]:
    """A project's portable, non-superseded durable (procedural/semantic) notes."""
    superseded = store.superseded_ids()
    out: list[Memory] = []
    for note_type in _DURABLE:
        out.extend(
            m
            for m in store.list(project=project, type=note_type, scope="portable")
            if m.id not in superseded
        )
    return out


def _render_notes(notes: list[Memory]) -> str:
    return "\n\n".join(f"## [{m.id}] [{m.type}] {m.title}\n{m.body}" for m in notes)


def _parse_merge(text: str, valid_ids: set[str]) -> list[MergeGroup]:
    """Parse and validate the model's JSON array of merge groups.

    ``valid_ids`` is the set of input note ids for the project. Raises ValueError on
    any bad shape, a hallucinated id (not in valid_ids), a keeper inside its own
    superseded_ids, or an id reused across groups. A raise aborts the project (nothing
    written) - mirrors reflect._parse_reflection.
    """
    data = json.loads(_strip_fences(text))
    if not isinstance(data, list):
        raise ValueError("merge output is not a JSON array")
    groups: list[MergeGroup] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("merge item is not an object")
        action = str(item.get("action", "")).strip()
        superseded = [str(i) for i in item.get("superseded_ids", [])]
        if action not in ("keep", "synthesize"):
            raise ValueError(f"invalid merge action: {action!r}")
        if not superseded:
            raise ValueError("merge group missing superseded_ids")
        group = MergeGroup(action=action, superseded_ids=superseded)
        if action == "keep":
            keeper_id = str(item.get("keeper_id", "")).strip()
            if not keeper_id:
                raise ValueError("keep group missing keeper_id")
            if keeper_id in superseded:
                raise ValueError("keep group lists its keeper_id as superseded")
            group.keeper_id = keeper_id
            group_ids = [keeper_id, *superseded]
        else:
            ntype = str(item.get("type", "")).strip()
            title = str(item.get("title", "")).strip()
            body = str(item.get("body", "")).strip()
            if ntype not in ("semantic", "procedural"):
                raise ValueError(f"invalid synthesize type: {ntype!r}")
            if not (title and body):
                raise ValueError("synthesize group missing title or body")
            group.type = ntype
            group.title = title
            group.body = body
            group_ids = list(superseded)
        for gid in group_ids:
            if gid not in valid_ids:
                raise ValueError(f"merge references unknown id: {gid!r}")
            if gid in seen:
                raise ValueError(f"merge reuses id across groups: {gid!r}")
            seen.add(gid)
        groups.append(group)
    return groups


@dataclass
class Merger:
    """Propose merge groups for a set of notes via an injected LLM client."""

    client: LLMClient
    model_label: str
    max_chars: int = _DEFAULT_MAX_CHARS

    def propose(self, notes: list[Memory]) -> list[MergeGroup]:
        content = _window(redact(_render_notes(notes)), self.max_chars)
        text = self.client(MERGE_SYSTEM_PROMPT, content)
        return _parse_merge(text, {m.id for m in notes})


def make_merger() -> Merger | None:
    """Build a Merger from config, or None when no provider/model/key is configured."""
    cfg = resolve_reflection_config()
    if not (cfg.model and cfg.base_url and cfg.api_key):
        return None
    client = _http_client(cfg.base_url, cfg.api_key, cfg.model, cfg.timeout)
    return Merger(
        client=client,
        model_label=f"{cfg.provider}/{cfg.model}",
        max_chars=cfg.max_tokens * 4,
    )


@dataclass
class MergeResult:
    """Outcome of merging one project."""

    project: str
    groups_applied: int
    notes_superseded: int
    notes_synthesized: int


def apply_merge(
    store: MemoryStore,
    project: str,
    merger: Merger,
    *,
    machine_id: str,
    confidence: float = _DEFAULT_CONFIDENCE,
) -> MergeResult:
    """Propose and apply merges for a project's durable notes.

    The LLM call happens first; if it raises or fails validation, nothing is written
    (no fallback). For 'keep', the survivor's supersedes grows by the group's ids
    (additive union) and it is tagged 'merged'. For 'synthesize', a new note is written
    with prov_source='merge' and all originals superseded.
    """
    notes = select_mergeable(store, project)
    groups = merger.propose(notes)
    superseded_count = 0
    synthesized_count = 0
    for group in groups:
        if group.action == "keep":
            keeper = store.get(group.keeper_id)
            keeper.supersedes = sorted(set(keeper.supersedes) | set(group.superseded_ids))
            keeper.tags = sorted(set(keeper.tags) | {"merged"})
            keeper.updated_at = _utcnow()
            store.put(keeper)
        else:
            store.write(
                type=group.type,
                title=group.title,
                body=group.body,
                project=project,
                machine_id=machine_id,
                scope="portable",
                tags=["merge"],
                prov_source="merge",
                prov_model=merger.model_label,
                confidence=confidence,
                supersedes=list(group.superseded_ids),
            )
            synthesized_count += 1
        superseded_count += len(group.superseded_ids)
    return MergeResult(
        project=project,
        groups_applied=len(groups),
        notes_superseded=superseded_count,
        notes_synthesized=synthesized_count,
    )
