"""Git-as-sync over Tailscale - the v0 sync layer (architecture §4).

``memory/`` is a git repo; sync = commit local changes, pull --rebase, push, over
a remote reachable on the user's Tailscale mesh (a bare repo on an always-on
node, or another machine directly). The SQLite index is never synced: it lives
outside ``memory/`` and is rebuilt locally, per the claude-brain corruption
lesson.

The backend is pluggable (the :class:`SyncBackend` Protocol) so direct
peer-to-peer or a libSQL path can slot in later without touching the server.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

_BRANCH = "main"


class SyncError(RuntimeError):
    """A git sync command failed unrecoverably."""


@dataclass
class SyncResult:
    """The outcome of a single :meth:`SyncBackend.sync`."""

    pushed: bool
    pulled: int
    conflicted: bool
    head: str
    detail: str


@dataclass
class SyncState:
    """A point-in-time view of the local repo, surfaced by ``memory_status``."""

    initialized: bool
    remote: str | None
    head: str
    dirty: bool
    detail: str


class SyncBackend(Protocol):
    """Pluggable sync mechanism (git-over-Tailscale today; P2P/libSQL later)."""

    def init(self) -> None: ...
    def sync(self) -> SyncResult: ...
    def state(self) -> SyncState: ...


class GitSyncBackend:
    """Sync a ``memory/`` directory as a git repo against a remote."""

    def __init__(self, repo_dir: Path | str, *, remote: str | None, machine_id: str) -> None:
        self.repo_dir = Path(repo_dir)
        self.remote = remote
        self.machine_id = machine_id

    # -- git plumbing ------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        ident = {
            "GIT_AUTHOR_NAME": "anamnesis",
            "GIT_AUTHOR_EMAIL": f"anamnesis@{self.machine_id}",
            "GIT_COMMITTER_NAME": "anamnesis",
            "GIT_COMMITTER_EMAIL": f"anamnesis@{self.machine_id}",
        }
        proc = subprocess.run(
            ["git", "-C", str(self.repo_dir), *args],
            capture_output=True,
            text=True,
            env={**os.environ, **ident},
        )
        if check and proc.returncode != 0:
            raise SyncError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc

    def _is_git(self) -> bool:
        return (self.repo_dir / ".git").is_dir()

    def _has_commits(self) -> bool:
        return self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode == 0

    def _remote_has_branch(self) -> bool:
        ref = self._git("rev-parse", "--verify", "--quiet", f"origin/{_BRANCH}", check=False)
        return ref.returncode == 0

    def _head(self) -> str:
        if not self._has_commits():
            return ""
        return self._git("rev-parse", "--short", "HEAD").stdout.strip()

    def _dirty(self) -> bool:
        return bool(self._git("status", "--porcelain").stdout.strip())

    # -- API ---------------------------------------------------------------

    def init(self) -> None:
        if not self._is_git():
            self._git("init", "-b", _BRANCH)
        if self.remote is not None:
            if self._git("remote", "get-url", "origin", check=False).returncode == 0:
                self._git("remote", "set-url", "origin", self.remote)
            else:
                self._git("remote", "add", "origin", self.remote)

    def sync(self) -> SyncResult:
        if not self._is_git():
            self.init()

        # 1. commit local changes (the markdown is the source of truth)
        self._git("add", "-A")
        committed = self._git("diff", "--cached", "--quiet", check=False).returncode != 0
        if committed:
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            self._git("commit", "-m", f"anamnesis: sync from {self.machine_id} at {stamp}")

        if self.remote is None:
            detail = "committed locally" if committed else "nothing to commit"
            return SyncResult(False, 0, False, self._head(), f"{detail}; no remote configured")

        # 2. integrate the remote (pull --rebase), then push
        self._git("fetch", "origin", check=False)
        pulled = 0
        if self._remote_has_branch():
            before = self._head()
            if not self._has_commits():
                self._git("reset", "--hard", f"origin/{_BRANCH}")
            else:
                rebase = self._git("rebase", f"origin/{_BRANCH}", check=False)
                if rebase.returncode != 0:
                    # v0 policy: surface the conflict, never silently drop. Abort the
                    # rebase (local edits stay in place) and leave it for resolution.
                    self._git("rebase", "--abort", check=False)
                    return SyncResult(
                        False,
                        0,
                        True,
                        self._head(),
                        "conflict on rebase; kept local edits, did not push - resolve and re-sync",
                    )
            after = self._head()
            if before and after != before:
                pulled = int(
                    self._git("rev-list", "--count", f"{before}..{after}", check=False).stdout or 0
                )

        push = self._git("push", "-u", "origin", _BRANCH, check=False)
        if push.returncode != 0:
            raise SyncError(f"git push failed: {push.stderr.strip()}")
        pushed = "up-to-date" not in (push.stderr + push.stdout).lower()
        return SyncResult(pushed, pulled, False, self._head(), "synced")

    def state(self) -> SyncState:
        if not self._is_git():
            return SyncState(False, self.remote, "", False, "not initialized")
        return SyncState(True, self.remote, self._head(), self._dirty(), "ok")
