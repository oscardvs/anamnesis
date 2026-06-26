<!-- bench/cross-machine-tokens/RUNBOOK.md -->
# Demo recording runbook (synthetic, no personal info)

Produces site/public/demo.mp4: a split-screen recording of two real machines on
the Tailscale mesh, using the synthetic quotes-api project and a throwaway store.

## Setup (both machines, throwaway store)

```bash
export ANAMNESIS_HOME=/tmp/anamnesis-demo
export ANAMNESIS_IMPORT_NATIVE=0
uv run --project server python bench/cross-machine-tokens/setup_synthetic.py \
  --store /tmp/anamnesis-demo --project-dir /tmp/quotes-api
```

Configure /tmp/anamnesis-demo with a throwaway git remote shared between the two
machines (a bare repo over Tailscale), exactly like a real setup but disposable.

## Recording beats

1. Left (desktop): a Claude Code session in /tmp/quotes-api establishes the
   conventions; Anamnesis captures + syncs them.
2. Right (laptop): a fresh session gets "Add a POST /quotes endpoint" and applies
   the conventions immediately because memory synced.
3. Optional: cut to the dashboard showing the synced notes.

Keep it short; export a compressed muted loop (target a few MB, H.264 .mp4).

## No-personal-info checklist (run before committing demo.mp4)

- [ ] Store is /tmp/anamnesis-demo, NOT ~/.anamnesis. Confirm on screen.
- [ ] Only the synthetic quotes-api project is visible. No other repos/files.
- [ ] On-screen machine labels are generic ("desktop" / "laptop"), not real hostnames.
- [ ] No real paths beyond a generic home; no terminal scrollback with personal data.
- [ ] No email, tokens, API keys, or .env contents on screen.
- [ ] Watch the full clip frame by frame once more before committing.
