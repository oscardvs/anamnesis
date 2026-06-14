# dashboard

The Anamnesis **memory GUI** - a git-like visual interface for your cross-machine memory. Next.js (App Router).

> 🚧 Scaffold only - built in **Phase 1** (after the MVP syncs). See the (local-only) `docs/roadmap.md`.

## What it does (planned)

- **Git-like history** of your memory (branch/tree view driven by the actual git log).
- **Machine list** with last-sync timestamps and sync-status badges.
- **Browse / search / edit** memory notes (markdown render + inline edit, writing back to the store).

It is a thin read/write client over the local memory store/API - and later, the optional hosted relay.
No business logic lives here that isn't also enforced by the server.

## Development

Scaffolding command (to be run when we start Phase 1):

```bash
# from repo root
npx create-next-app@latest dashboard --ts --app --eslint
```
