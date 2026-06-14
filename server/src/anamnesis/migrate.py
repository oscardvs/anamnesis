"""One-time project re-key migration onto a stable cross-machine key scheme
(architecture section 10.2).

Generic and data-driven: callers pass a memory directory plus a project map and
per-note id overrides. No hardcoded paths or personal keys, so the logic is
public and tested on synthetic fixtures; it touches the real store only at
runtime, the same posture as capture.py. Markdown is the source of truth and only
the ``project:`` line changes (body, ``updated_at``, and every other field are
preserved), so ``git diff`` shows exactly one line per note and the memory repo's
history is the undo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_FM_DELIM = "---\n"
_PROJECT_LINE = re.compile(r"^project:.*$", re.MULTILINE)


@dataclass
class Change:
    """A single planned or applied re-key of one note's project field."""

    id: str
    type: str
    old_project: str
    new_project: str


def rekey_front_matter(text: str, new_project: str) -> str:
    """Return ``text`` with only the front-matter ``project:`` line set anew.

    Operates inside the YAML front-matter block only, so a ``project:`` line in
    the body is never touched. The new value is written as a plain YAML scalar;
    every project key in use (for example ``github.com/oscardvs/anamnesis``,
    ``ros2_ws``, ``global``) is a valid unquoted scalar. Raises ``ValueError`` if
    the text has no front-matter or no ``project:`` line. Idempotent: if the
    project already equals ``new_project`` the returned text is identical.
    """
    if not text.startswith(_FM_DELIM):
        raise ValueError("note has no YAML front-matter")
    front_str, sep, body = text[len(_FM_DELIM) :].partition("\n" + _FM_DELIM)
    if not sep:
        raise ValueError("unterminated front-matter")
    if not _PROJECT_LINE.search(front_str):
        raise ValueError("front-matter has no project field")
    new_front = _PROJECT_LINE.sub(f"project: {new_project}", front_str, count=1)
    return _FM_DELIM + new_front + sep + body
