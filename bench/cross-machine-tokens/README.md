<!-- bench/cross-machine-tokens/README.md -->
# Cross-machine token benchmark

Measures the honest token cost of completing one task on a fresh machine WITHOUT
Anamnesis (the agent explores the project to learn its conventions) versus WITH
Anamnesis (the real SessionStart memory block is injected). Synthetic project and
store only, no personal data.

## Reproduce

1. Prereqs: Node.js >=18 and the Claude Code CLI (`claude`), logged in. A Pro/Max
   subscription works and no Anthropic Console API key is needed (the harness
   drives `claude -p` on your existing login). Confirm with:
   `claude -p "ok" --output-format json`.
2. Set up the synthetic project + store:
   ```bash
   ANAMNESIS_IMPORT_NATIVE=0 uv run --project server python \
     bench/cross-machine-tokens/setup_synthetic.py \
     --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api
   ```
3. Run the measurement (averages several runs; agentic runs are non-deterministic).
   Each run uses a throwaway CLAUDE_CONFIG_DIR (copied credentials + hook-free
   settings), so your global Claude Code hooks never fire and your live config is
   untouched:
   ```bash
   ANAMNESIS_IMPORT_NATIVE=0 uv run --project server python \
     bench/cross-machine-tokens/measure_tokens.py \
     --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api \
     --model claude-opus-4-8 --repeats 3
   ```
4. Render the chart from the result:
   ```bash
   uv run --project server python bench/cross-machine-tokens/make_chart.py \
     --in bench/cross-machine-tokens/result.json
   ```

## Honesty

The warm run injects the EXACT block `anamnesis inject` prints; the cold run is
identical except it has no memory. Both may read/explore files freely. We report
the measured delta as-is and never tune the scenario to inflate it.
