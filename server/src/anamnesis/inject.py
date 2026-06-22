"""SessionStart memory injection: select and render notes for a project.

Pure reads over :class:`MemoryStore` (no FastMCP, no network). ``resolve_project_key``
derives a v0 project identity from the working directory; a stable cross-machine
identity (git remote / repo marker) is a planned follow-up, deliberately isolated
in this one function.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from anamnesis.store import Memory, MemoryStore

_DURABLE = ("procedural", "semantic")
_MAX_EPISODIC = 2


def _normalize_remote(url: str) -> str:
    """Normalize a git remote URL to a stable lowercased key (no scheme/user/.git)."""
    u = url.strip()
    u = re.sub(r"^\w+://", "", u)  # strip scheme: https:// ssh:// git://
    u = re.sub(r"^[^@/]+@", "", u)  # strip user@
    if ":" in u and "/" not in u.split(":", 1)[0]:
        u = u.replace(":", "/", 1)  # scp form host:path -> host/path
    u = re.sub(r"\.git$", "", u)
    return u.rstrip("/").lower()


def _read_marker(cwd: Path) -> str | None:
    """First non-empty line of the nearest ``.anamnesis/project`` marker, or None.

    Searched from ``cwd`` upward, stopping below the home directory (and the
    filesystem root) so a stray marker at ``$HOME`` cannot hijack every project.
    Best-effort: read errors are ignored.
    """
    home = Path.home()
    for d in [cwd, *cwd.parents]:
        if d == home or d == d.parent:
            break
        marker = d / ".anamnesis" / "project"
        try:
            if marker.is_file():
                for raw in marker.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if line:
                        return line
        except OSError:
            pass
    return None


def resolve_project_key(cwd: str | Path) -> str:
    """Best-effort stable project key from a working directory.

    Order: ``.anamnesis/project`` marker (searched up-tree), else normalized
    ``origin`` remote, else repo-root dirname, else cwd basename. The marker is
    the explicit, cross-machine-stable override (architecture section 10.2),
    notably for non-git workspaces where a subdir would otherwise resolve to its
    bare basename.
    """
    cwd = Path(cwd)
    marker = _read_marker(cwd)
    if marker:
        return marker
    try:
        remote = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if remote.returncode == 0 and remote.stdout.strip():
            return _normalize_remote(remote.stdout.strip())
        root = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if root.returncode == 0 and root.stdout.strip():
            return Path(root.stdout.strip()).name.lower()
    except OSError:
        pass
    return (cwd.name or "global").lower()


def select_inject(store: MemoryStore, *, project: str, k: int = 8) -> list[Memory]:
    """Notes to inject at SessionStart.

    All ``global`` notes (always, in full) plus up to ``k`` project notes: recent
    durable (procedural/semantic) notes fill the budget, reserving up to two of the
    most recent episodic notes for the "what I last did" continuity thread. Superseded
    notes are hidden (still browsable via ``list``); already-reflected episodics are
    dropped (their content is in the durable notes); confidence breaks recency ties.
    """
    superseded = store.superseded_ids()
    global_notes = [m for m in store.list(project="global") if m.id not in superseded]
    durable: list[Memory] = []
    for note_type in _DURABLE:
        durable.extend(store.list(project=project, type=note_type))
    durable = [m for m in durable if m.id not in superseded]
    durable.sort(key=lambda m: (m.updated_at, m.confidence), reverse=True)
    episodic = [
        m
        for m in store.list(project=project, type="episodic")
        if m.id not in superseded and "reflected" not in m.tags
    ][:_MAX_EPISODIC]

    budget = max(0, k)
    reserve = min(len(episodic), budget)
    durable_sel = durable[: budget - reserve]
    project_sel = durable_sel + episodic[:reserve]

    out: list[Memory] = []
    seen: set[str] = set()
    for m in [*global_notes, *project_sel]:
        if m.id not in seen:
            seen.add(m.id)
            out.append(m)
    return out


def render_inject(memories: list[Memory]) -> str:
    """Render selected notes as one markdown block for SessionStart stdout."""
    if not memories:
        return ""
    lines = ["# Anamnesis memory (auto-injected)", ""]
    for m in memories:
        lines.append(f"## [{m.type}] {m.title}")
        meta = f"_project: {m.project} | origin: {m.machine_id}"
        if m.prov_source != "human" or m.confidence < 1.0:
            meta += f" | source: {m.prov_source} (confidence {m.confidence:g})"
        meta += "_"
        lines.append(meta)
        lines.append("")
        if m.body:
            lines.append(m.body)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
