# Repository Guidelines

## Project Progress

- **Use feature name only** to determine project progress. See `docs/backlog.md` for the canonical list; status is tracked per feature (e.g. Hybrid Search Optimization, Context Optimization), not by phases or stage numbers.

## Project Structure & Module Organization

- `packages/rust/crates/*`: Rust core crates (for example `omni-vector`, `omni-scanner`, `omni-knowledge`).
- `packages/rust/bindings/python`: PyO3 bridge crate (`omni-core-rs`) used by Python services.
- `packages/python/agent`, `packages/python/core`, `packages/python/foundation`, `packages/python/mcp-server`: main Python runtime and APIs.
- `assets/skills/*`: skill implementations (`scripts/`), skill tests, and metadata-driven command surface.
- `docs/`: architecture, testing, and reference docs.
- `tests/` and `packages/**/tests/`: integration and unit test suites.

## Build, Test, and Development Commands

- `just setup && omni sync`: initial bootstrap.
- `uv sync`: install/update Python workspace dependencies.
- `uv sync --reinstall-package omni-core-rs`: rebuild and reinstall Rust Python bindings after Rust bridge changes.
- `cargo test -p omni-vector`: run targeted Rust tests (use crate-specific runs during development).
- `uv run pytest packages/python/core/tests/ -q`: run Python tests by package.
- `devenv test`: repository-level validation suite.
- `just agent-fmt`: run formatting hooks quickly.

## Coding Style & Naming Conventions

- Python: Ruff-enforced style (`line-length = 100`, Python 3.13 target, double quotes, space indent).
- Rust: `rustfmt` (edition 2024) and strict lints (`unwrap_used`/`expect_used` denied in workspace clippy config).
- Test naming: `test_*.py` and Rust `#[tokio::test]`/`#[test]` with descriptive names.
- Prefer explicit, domain-based names such as `router.search_tools`, `knowledge.recall`, `git.smart_commit`.

## Modularization Rules

- **Split by complexity, not line count**: When a module handles multiple distinct concerns (e.g. CRUD + query algorithms + persistence + deduplication), split it into sub-modules — regardless of file size. A 200-line file with mixed concerns should be split; a 600-line file with a single focused concern can stay.
- **Namespace must reflect feature/domain intent**: Sub-module names should map to the feature or capability they implement, not generic labels. Use domain-specific names that are unambiguous in the project context:
  - Good: `graph/query.rs` (search algorithms), `graph/skill_registry.rs` (Bridge 4 bulk registration), `graph/persistence.rs` (JSON save/load)
  - Bad: `graph/utils.rs`, `graph/helpers.rs`, `graph/misc.rs`
- **Re-export from `mod.rs`**: Public types and functions must be re-exported so callers use the parent module path without knowing the internal layout.
- **Field visibility**: Use `pub(crate)` for struct fields that sub-modules need; avoid `pub` unless it's part of the public API.
- **Test placement**: Never put `#[cfg(test)] mod tests { ... }` inline in complex modules. Place tests in `tests/test_<module>.rs` (integration tests) or `<module>/tests.rs` (unit tests). This keeps source files focused and tests independently runnable.
- **No hardcoded values in tests**: Use named constants, fixtures, `pytest.approx()`, and centralized path helpers instead of magic numbers or `parents[N]` traversal.

## Testing Guidelines

- Pytest config is strict and parallelized (`-n auto`, capped workers, timeout defaults).
- Run narrow tests before full suite, then validate cross-layer changes (Rust + Python).
- For routing/vector changes, test both data contracts and CLI behavior.
- Use focused commands, for example:
  - `uv run pytest packages/python/agent/tests/unit/cli/test_route_command.py -q`
  - `cargo test -p omni-vector --test test_rust_cortex`

## Commit & Pull Request Guidelines

- Commit messages are enforced by `conform`/`cog check`; use Conventional Commits.
- Prefer scoped messages aligned with `cog.toml` scopes, e.g. `feat(router): ...`, `fix(omni-vector): ...`, `docs(cli): ...`.
- Run `lefthook run pre-commit --all-files` (or `just agent-fmt`) before committing.
- PRs should include:
  - clear problem/solution summary,
  - changed paths/modules,
  - test evidence (exact commands + outcomes),
  - screenshots/CLI output when behavior changes are user-facing.

## Security & Configuration Tips

- Do not commit secrets; keep environment/local overrides outside tracked files.
- Keep generated artifacts and caches out of commits unless intentionally versioned.
