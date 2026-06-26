"""Pure logic for the cross-machine token-cost benchmark.

Synthetic only: no real project, no real memory. See RUNBOOK.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScenarioNote:
    type: str
    title: str
    body: str
    project: str
    tags: list[str] = field(default_factory=list)


# The four notes Anamnesis has "captured" for the synthetic quotes-api project.
# Conventions a correct POST /quotes must follow, plus one global preference.
SCENARIO: list[ScenarioNote] = [
    ScenarioNote(
        type="procedural",
        title="API errors use a standard envelope",
        body=(
            "Every API error response is the JSON object "
            '`{ "error": { "code": <snake_case_string>, "message": <human string> } }` '
            "with the matching HTTP status. Codes are snake_case (invalid_body, not_found, "
            "conflict). Never return a bare string or a differently shaped error object."
        ),
        project="quotes-api",
        tags=["convention", "errors", "api"],
    ),
    ScenarioNote(
        type="procedural",
        title="Validate request bodies with zod at the route boundary",
        body=(
            "Validate every request body with a zod schema at the route boundary, before "
            "calling into handlers. Handlers receive already-parsed, typed input and never "
            "re-validate. On a zod failure return the standard error envelope with code "
            "invalid_body and HTTP 400."
        ),
        project="quotes-api",
        tags=["convention", "validation", "zod"],
    ),
    ScenarioNote(
        type="procedural",
        title="Database access only through db/repo.ts",
        body=(
            "All database access goes through functions exported from db/repo.ts (for example "
            "createQuote, listQuotes). Route handlers never import the database client "
            "directly; they call repo functions. This keeps data access in one place."
        ),
        project="quotes-api",
        tags=["convention", "architecture", "database"],
    ),
    ScenarioNote(
        type="semantic",
        title="No AI attribution in commits or comments",
        body=(
            "Write plain comments and commit messages with no AI attribution lines: no "
            "Co-Authored-By, no Generated with, no robot emoji."
        ),
        project="global",
        tags=["preference", "style"],
    ),
]


def seed_store(home: Path) -> int:
    """Write the SCENARIO notes into a fresh store under ``home`` and reindex.

    Uses the real anamnesis store so the markdown + index match production exactly.
    Returns the number of notes indexed.
    """
    from anamnesis.store import MemoryStore

    store = MemoryStore(root=home)
    try:
        for note in SCENARIO:
            store.write(
                type=note.type,
                title=note.title,
                body=note.body,
                project=note.project,
                machine_id="desktop",
                tags=list(note.tags),
            )
        return store.reindex()
    finally:
        store.close()
