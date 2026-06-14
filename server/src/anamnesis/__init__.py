"""Anamnesis - cross-machine, file-first memory layer for Claude Code.

This package is the MCP memory server. Memory is stored as markdown (the source
of truth) plus a locally-rebuilt SQLite FTS5 index, synced across the user's own
machines via git over a Tailscale mesh.

Design notes live in the repo's CLAUDE.md and (local-only) docs/architecture.md.
"""

__version__ = "0.0.1"
