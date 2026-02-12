# Repository Guidelines

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
