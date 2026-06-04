# Incident Log

## 2026-05-29 - `apps/web` Next/Turbopack fatal OOM

### Summary

The fatal Node.js out-of-memory crash was caused by **agent-introduced package manager contamination** in `apps/web`.

`apps/web` is an npm-managed frontend. I ran pnpm-based commands against it and left pnpm workspace artifacts in place. That changed the local dependency layout into a mixed npm/pnpm state and caused Next.js/Turbopack to blow up during compile.

The crash was observed in:

- [apps/web-dev.log](/E:/AI/My-Project/Enterprise KnowledgeBase/apps/web-dev.log)

Key evidence from the log:

- `Compiling /retrieval ...`
- `Fatal process out of memory: Worklist::Segment::Create`
- `Fatal process out of memory: Re-embedded builtins: set permissions`

### Root cause

I introduced a mixed package-manager state under `apps/web`:

- npm lockfile already existed: `apps/web/package-lock.json`
- I then introduced pnpm artifacts:
  - `apps/web/pnpm-lock.yaml`
  - `apps/web/pnpm-workspace.yaml`
- pnpm also rewrote local install layout into `.pnpm/` and `.ignored/`

That combination is not a harmless metadata mismatch. It changes how dependencies are laid out on disk and how the dev toolchain resolves the workspace. In this state, compiling the frontend with Next.js/Turbopack became unstable and eventually OOMed.

### Why this error happened

I made two process mistakes:

1. I did **not verify the package manager already in use** before running frontend validation commands.
2. I used a tool-driven command (`pnpm ...`) on an npm-managed app in a repo that already had multiple lockfile contexts.

The second mistake is what made this severe. It did not just fail a command. It mutated the local frontend install state.

### What was changed to stop recurrence in the repo

- Removed:
  - `apps/web/pnpm-lock.yaml`
  - `apps/web/pnpm-workspace.yaml`
  - root `package-lock.json`
- Restored `apps/web/package.json` dev script from forced high-memory mode back to:
  - `next dev`

### Required operator cleanup

The repository-side fix is not enough to clean the already-mutated local install tree.

Local cleanup still required before anyone runs the frontend again:

1. Delete `apps/web/node_modules`
2. Reinstall with **npm only** from `apps/web`
3. Do not run pnpm commands in `apps/web`

### Rule going forward

For `apps/web`, package-manager choice must be treated as part of runtime integrity:

- `npm` only unless the project is explicitly migrated
- do not introduce a second lockfile family
- do not run package-manager-specific validation commands before checking the existing lockfile and install layout

此规则已纳入 `apps/web/AGENTS.md` 作为 agent 操作约束。
