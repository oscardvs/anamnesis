"""Measure cross-machine token cost: same task, cold vs memory-injected.

Drives the REAL Claude Code agent headlessly via `claude -p --output-format json`
(not the Agent SDK), so it runs on your existing Claude Code login: a Pro/Max
subscription works and you do NOT need an Anthropic Console API key. (The Agent
SDK requires an API key; the Claude Code CLI itself authenticates with the
subscription and reports per-session token usage in its JSON result, the same
numbers your status line shows.)

Each run uses a throwaway CLAUDE_CONFIG_DIR (a copy of your credentials plus an
empty, hook-free settings.json), so your global Claude Code hooks never fire
during measurement. This matters for correctness and safety: the Anamnesis
SessionStart hooks would otherwise inject your real memory into the "cold" run
and run a sync whose inline remote is your real memory repo. Isolating the
config prevents both, without touching your live ~/.claude config.

Reproducibility prerequisites (synthetic only):
  - Node.js >=18 and the Claude Code CLI (`claude`), logged in (subscription or
    API key). Confirm with: claude -p "ok" --output-format json
  - a synthetic store + project from setup_synthetic.py

Run (from repo root):
  ANAMNESIS_IMPORT_NATIVE=0 uv run --project server python \
    bench/cross-machine-tokens/measure_tokens.py \
    --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api \
    --model claude-opus-4-8 --repeats 3 --out bench/cross-machine-tokens/result.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
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


def parse_cli_usage(stdout: str) -> dict:
    """Extract the ``usage`` dict from a `claude -p --output-format json` result.

    Raises RuntimeError if the run errored or carried no usage, so a failed
    measurement is loud rather than silently recorded as zero tokens.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude returned non-JSON output: {stdout[-500:]}") from e
    if data.get("is_error"):
        raise RuntimeError(
            f"claude run failed: subtype={data.get('subtype')} "
            f"api_error_status={data.get('api_error_status')}"
        )
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise RuntimeError("claude result carried no usage object")
    return usage


@contextmanager
def isolated_claude_config() -> Iterator[str]:
    """A throwaway CLAUDE_CONFIG_DIR: copied credentials + hook-free settings.

    Lets `claude -p` authenticate with your existing login while loading none of
    your user-scope hooks/MCP, so measurement runs are clean and your real memory
    sync can never fire. (It does not redirect enterprise managed-settings such as
    /etc/claude-code/managed-settings.json; an individual on a subscription has
    none.) Cleaned up on exit (removes the credential copy).
    """
    src = Path.home() / ".claude" / ".credentials.json"
    if not src.exists():
        raise RuntimeError(
            "no ~/.claude/.credentials.json found. Run `claude` and log in first, "
            "or, if this machine stores auth in an OS keychain, point "
            "CLAUDE_CONFIG_DIR at a hook-free config yourself and remove this gate."
        )
    cfg = tempfile.mkdtemp(prefix="bench-claude-cfg-")
    try:
        os.chmod(cfg, 0o700)
        shutil.copy2(src, Path(cfg) / ".credentials.json")
        (Path(cfg) / "settings.json").write_text("{}\n", encoding="utf-8")
        yield cfg
    finally:
        shutil.rmtree(cfg, ignore_errors=True)


def _cli_runner(project_dir: str, model: str, config_dir: str):
    """Return a runner: one headless `claude -p` task -> its usage dict."""
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = config_dir

    def run(prompt: str) -> dict:
        # --allowedTools restricts the agent to read + edit (no Bash), matching
        # the prior SDK runner so cold and warm stay comparable and the agent does
        # not shell out. The prompt is one argv element: the k=8 inject block is a
        # couple of KB, far under Linux MAX_ARG_STRLEN (128 KiB); a much larger
        # store would need stdin instead.
        proc = subprocess.run(
            [
                "claude",
                "-p",
                prompt,
                "--output-format",
                "json",
                "--model",
                model,
                "--allowedTools",
                "Read Glob Grep Write Edit",
                "--dangerously-skip-permissions",
            ],
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=1200,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[-500:]}")
        return parse_cli_usage(proc.stdout)

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
    with isolated_claude_config() as cfg:
        runner = _cli_runner(args.project_dir, args.model, cfg)
        out = run_experiment(runner, block, args.repeats)
    out["model"] = args.model
    Path(args.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
