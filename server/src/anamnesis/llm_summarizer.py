"""LLM-backed episodic summarizer (the swappable reflection model, architecture
section 6). Sends a redacted, size-bounded transcript to any OpenAI-compatible
endpoint and parses a strict-JSON summary. Provider, model, and URL come entirely
from config; nothing about any provider is hardcoded. Any failure falls back to
the deterministic heuristic so capture never breaks session teardown.

The runtime HTTP client uses stdlib ``urllib`` so the base (hook) install needs
no extra dependency. Tests inject a fake client and never touch the network.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from anamnesis.capture import HeuristicSummarizer, ParsedSession, Summarizer
from anamnesis.redact import redact

LLMClient = Callable[[str, str], str]

SYSTEM_PROMPT = (
    "You are a memory summarizer for a developer's coding assistant. You are given "
    "the transcript of one Claude Code session (messages and tool calls). Distill it "
    "into a single durable note for future sessions.\n\n"
    "Return ONLY a JSON object, no prose, with exactly these keys:\n"
    '{"skip": <true|false>, "title": <string>, "body": <string>}\n\n'
    "Set skip to true when the session produced nothing worth remembering later: "
    "trivial chit-chat, a question answered with no lasting decision, aborted or empty "
    "work. When in doubt, prefer skip=false.\n\n"
    "When skip is false:\n"
    "- title: a short, specific one-line summary (max ~80 chars), no trailing period.\n"
    "- body: markdown. Cover, only where present: what was accomplished, key decisions "
    "and WHY, gotchas or pitfalls discovered, and files changed. Be concise (aim under "
    "200 words). Omit greetings and chit-chat.\n\n"
    "Never include secrets, API keys, tokens, or credentials in your output."
)

_DEFAULT_MAX_CHARS = 480_000  # ~120k tokens at ~4 chars/token (SessionEnd is inline)
_DEFAULT_TOOL_RESULT_CAP = 2_000


def _window(text: str, max_chars: int) -> str:
    """Bound transcript size: keep head + tail with an explicit elision marker."""
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    return f"{text[:head]}\n\n...[transcript truncated for length]...\n\n{text[-tail:]}"


def _truncate_one(content: object, cap: int) -> object:
    if isinstance(content, str) and len(content) > cap:
        return content[:cap] + " ...[truncated]"
    if isinstance(content, list):
        return [_truncate_one(b, cap) for b in content]
    if isinstance(content, dict):
        out = dict(content)
        inner = out.get("content")
        if isinstance(inner, str) and len(inner) > cap:
            out["content"] = inner[:cap] + " ...[truncated]"
        elif isinstance(inner, list):
            out["content"] = [_truncate_one(b, cap) for b in inner]
        return out
    return content


def _truncate_tool_results(raw: str, cap: int) -> str:
    """Cap oversized tool_result blobs per line; tolerate non-JSON lines verbatim."""
    out: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            ev = json.loads(stripped)
        except json.JSONDecodeError:
            out.append(line)
            continue
        msg = ev.get("message") if isinstance(ev, dict) else None
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                msg["content"] = [
                    _truncate_one(b, cap)
                    if isinstance(b, dict) and b.get("type") == "tool_result"
                    else b
                    for b in content
                ]
        out.append(json.dumps(ev))
    return "\n".join(out)


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return cleaned.strip()


def _parse_summary(text: str) -> tuple[bool, str, str]:
    """Parse the model's JSON summary. Raises ValueError on a bad shape."""
    data = json.loads(_strip_fences(text))
    if not isinstance(data, dict):
        raise ValueError("summary is not a JSON object")
    skip = bool(data.get("skip", False))
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    if not skip and not (title and body):
        raise ValueError("non-skip summary missing title or body")
    return skip, title, body


@dataclass
class LLMSummarizer:
    """Summarize a session via an injected LLM client; fall back to heuristic."""

    client: LLMClient
    model_label: str
    max_chars: int = _DEFAULT_MAX_CHARS
    tool_result_cap: int = _DEFAULT_TOOL_RESULT_CAP
    fallback: Summarizer = field(default_factory=HeuristicSummarizer)

    def summarize(self, session: ParsedSession) -> tuple[str, str] | None:
        try:
            transcript = _truncate_tool_results(session.raw, self.tool_result_cap)
            content = _window(redact(transcript), self.max_chars)
            text = self.client(SYSTEM_PROMPT, content)
            skip, title, body = _parse_summary(text)
            if skip:
                return None
            return title, f"{body}\n\n_summarized by {self.model_label}_"
        except Exception as exc:  # noqa: BLE001 - capture must never break teardown
            print(f"capture: llm summary failed ({exc}); using heuristic", file=sys.stderr)
            return self.fallback.summarize(session)
