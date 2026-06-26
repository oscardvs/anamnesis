"""Measure cross-machine token cost: same task, cold vs memory-injected.

Reproducibility prerequisites (synthetic only):
  - Node.js >=18 and the Claude Code CLI: npm install -g @anthropic-ai/claude-code
  - pip dep: claude-agent-sdk (added ephemerally via uv --with below)
  - export ANTHROPIC_API_KEY=sk-ant-...
  - a synthetic store + project from setup_synthetic.py

Run (from repo root):
  ANAMNESIS_IMPORT_NATIVE=0 ANTHROPIC_API_KEY=sk-ant-... \
  uv run --project server --with claude-agent-sdk --with anyio python \
    bench/cross-machine-tokens/measure_tokens.py \
    --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api \
    --model claude-opus-4-8 --repeats 3 --out bench/cross-machine-tokens/result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lib

MODEL_DEFAULT = "claude-opus-4-8"


def inject_block(store: Path, project: str = "quotes-api", k: int = 8) -> str:
    """Capture the REAL SessionStart inject block from the synthetic store.

    Calls the same select_inject + render_inject the `anamnesis inject` CLI uses
    (no subprocess), so the warm run is injected exactly what SessionStart would.
    """
    from anamnesis.inject import render_inject, select_inject
    from anamnesis.store import MemoryStore

    s = MemoryStore(root=store)
    try:
        return render_inject(select_inject(s, project=project, k=k))
    finally:
        s.close()


def run_experiment(runner, inject_block: str, repeats: int) -> dict:
    """Run the task ``repeats`` times cold and ``repeats`` times warm."""
    cold_runs = [lib.parse_usage(runner(lib.TASK_PROMPT)) for _ in range(repeats)]
    warm_prompt = lib.build_warm_prompt(inject_block)
    warm_runs = [lib.parse_usage(runner(warm_prompt)) for _ in range(repeats)]
    cold = lib.summarize_runs("cold", cold_runs)
    warm = lib.summarize_runs("warm", warm_runs)
    return {
        "cold": cold,
        "warm": warm,
        "delta": {
            "total_input": cold["avg_total_input"] - warm["avg_total_input"],
            "output_tokens": cold["avg_output_tokens"] - warm["avg_output_tokens"],
        },
    }


def _sdk_runner(project_dir: str, model: str):
    """The real runner: one headless Agent SDK task, returns its usage dict."""
    import anyio
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    def run(prompt: str) -> dict:
        async def _go() -> dict:
            options = ClaudeAgentOptions(
                model=model,
                cwd=project_dir,
                allowed_tools=["Read", "Glob", "Grep", "Write", "Edit"],
                permission_mode="bypassPermissions",
                system_prompt="You are a careful software engineer.",
                setting_sources=[],  # do NOT load any CLAUDE.md / settings
                max_turns=20,
            )
            result = None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result = message
            assert result is not None, "no ResultMessage returned"
            return result.usage or {}

        return anyio.run(_go)

    return run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure cold vs warm token cost")
    ap.add_argument("--store", required=True)
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default="bench/cross-machine-tokens/result.json")
    args = ap.parse_args(argv)

    block = inject_block(Path(args.store))
    if not block.strip():
        print("error: empty inject block - is the store seeded?", file=sys.stderr)
        return 1
    runner = _sdk_runner(args.project_dir, args.model)
    out = run_experiment(runner, block, args.repeats)
    out["model"] = args.model
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
