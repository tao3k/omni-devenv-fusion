# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This repository uses **devenv** (https://devenv.sh) for managing the development environment with Nix. The environment is automatically loaded via direnv when entering the directory.

### Essential Commands

**Environment Setup:**
```bash
# Enter the development shell (automatic via direnv)
devenv shell

# Run tests
devenv test

# Update dependencies
devenv update
```

**Testing:**
```bash
# Run the test suite (defined in enterTest)
devenv test
# Tests verify git version matches the package version
```

**Git Hooks:**
```bash
# Git hooks are automatically managed via devenv's git-hooks integration
# Hooks run automatically on commit, but can be triggered manually:
pre-commit run --all-files  # Run all hooks
lefthook run                 # Alternative hook runner
```

## Architecture

### Nix Configuration Structure

- **devenv.nix**: Main devenv configuration defining packages, scripts, environment variables, and git hooks
- **devenv.yaml**: Flake inputs configuration, specifying nixpkgs source and external dependencies (omnibus)
- **devenv.lock**: Lock file for reproducible builds
- **.envrc**: direnv configuration that loads the devenv environment automatically

### Claude Code Integration

This repository has Claude Code integration built directly into the devenv configuration:

**Location:** `devenv.nix:10-24`

The integration enables:
- `claude.code.enable = true`: Activates Claude Code support (line 14)
- **PostToolUse Hook**: Automatically runs `lefthook run` after Claude Code tool usage, ensuring code quality checks are executed (lines 15-21)

**Hook Configuration:** `.claude/settings.json` defines two PostToolUse hooks:
1. Runs `lefthook run` after any tool use (lines 3-12)
2. Runs `pre-commit run` specifically after Edit/MultiEdit/Write operations (lines 13-22)

This means code quality checks (nixfmt, shellcheck) are automatically enforced when Claude Code modifies files.

### Git Hooks

**Enabled Hooks** (configured in `devenv.nix:66-67`):
- **shellcheck**: Lints shell scripts for common issues (line 66)
- **nixfmt**: Formats all `.nix` files automatically (line 67)

The hooks are managed by devenv's git-hooks integration and configured via pre-commit framework. The actual hook configuration is generated at `.pre-commit-config.yaml` (symlinked to Nix store).

### Available Packages

Core packages installed (from `devenv.nix:30-33`):
- `git`: Version control (line 31)
- `claude-code`: Claude Code CLI tool (line 32)

### Scripts

**hello script** (`devenv.nix:45-47`):
- Prints "hello from $GREET" (where GREET=devenv)
- Run with: `hello`

### Environment Variables

- **GREET**: Set to "devenv" (line 27), used by the hello script and enterShell message (line 50)

## Code Modification Guidelines

When modifying `.nix` files:
- Ensure proper Nix syntax and formatting (nixfmt will auto-format)
- Git hooks will automatically run on file changes via Claude Code's PostToolUse hooks
- Configuration follows devenv's modular structure with imports

When adding new packages:
- Add to `packages = [ ... ]` list in `devenv.nix:30-33`

When configuring new git hooks:
- Add to `git-hooks.hooks.<hook-name>` in `devenv.nix` (see lines 66-67 for examples)

## Flake Inputs

The repository uses custom flake inputs defined in `devenv.yaml:2-7`:
- **nixpkgs**: Rolling release from cachix/devenv-nixpkgs
- **omnibus**: Custom input from tao3k/omnibus (main branch)

The `allowUnfree: true` setting permits unfree packages.
