"""Measurement harness: retrieval recall and working-set shrink (Phase 2 gate b).

Generic and public (the native_import.py contract): no hardcoded personal paths,
synthetic-fixture tests, touches the real store only at runtime. The eval set and
any sandbox/report live under the store root, outside the repo. See the design
doc (docs/superpowers/specs/2026-06-23-measurement-harness-design.md, local-only).
"""

from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Provider-agnostic token estimate: the ~4-chars/token heuristic.

    The harness only ever reports ratios and diffs of this same estimator, which
    are robust to the constant factor, so we deliberately avoid a real (networked,
    provider-specific) tokenizer. One isolated function, swappable if needed.
    """
    return math.ceil(len(text) / 4)
