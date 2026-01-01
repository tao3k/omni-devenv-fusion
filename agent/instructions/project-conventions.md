# Project Conventions

> Universal project instructions for any LLM CLI (Claude, Gemini, OpenAI, etc.)

## 1. Temporary Files → Follow prj-spec

All auto-generated/temporary files MUST follow [numtide/prj-spec](https://github.com/numtide/prj-spec):

| Directory | Purpose |
|-----------|---------|
| `.cache/` | Caches, build artifacts, temporary data |
| `.config/` | Auto-generated configs (nixago outputs) |
| `.data/` | Runtime data, databases |
| `.run/` | PID files, runtime state |
| `.bin/` | Generated binaries, scripts |

**Rules:**

- Temporary files go in `.cache/<project-name>/` or subdirectories
- `.gitignore` must exclude prj-spec directories
- **SCRATCHPAD.md** → `.cache/omni-devenv-fusion/.memory/active_context/SCRATCHPAD.md`
- **Session logs** → `.cache/omni-devenv-fusion/.memory/sessions/`

## 2. Environment Isolation

Use devenv/direnv for all development tasks:

| Command | Purpose |
|---------|---------|
| `direnv reload` | Reload environment after `.envrc` changes |
| `devenv shell` | Enter isolated development shell |
| `devenv up` | Start devenv services |

**Workflow:**

1. `cd` into project → direnv auto-loads (`.envrc`)
2. Changes to `.envrc` → run `direnv reload`
3. Need isolated shell → `devenv shell`
4. Dependencies managed by devenv.nix + pyproject.toml (UV)

## 3. Related Documentation

| File | Purpose |
|------|---------|
| `agent/how-to/git-workflow.md` | Git operations and commit protocol |
| `agent/standards/feature-lifecycle.md` | Spec-driven development workflow |
| `agent/writing-style/` | Writing standards |
