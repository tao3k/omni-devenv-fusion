# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

This repository uses **devenv** (https://devenv.sh) for managing the development environment with Nix. The environment is automatically loaded via direnv when entering the directory.

### Essential Commands

**Quick Start (using Justfile):**
```bash
# Show all available commands
just

# Setup environment
just setup

# Validate everything (format, commits, lint, test)
just validate

# Preview changelog
just changelog-preview

# Bump version and release
just release
```

**Environment Setup:**
```bash
# Enter the development shell (automatic via direnv)
devenv shell

# Run tests
devenv test  # or: just test

# Update dependencies
devenv update  # or: just update
```

**Testing:**
```bash
# Run the test suite (defined in enterTest)
devenv test  # or: just test
# Tests verify git version matches the package version
```

**Git Hooks:**
```bash
# Git hooks are managed via lefthook (omnibus framework)
# Hooks run automatically on commit, triggered manually with:
lefthook run  # or: just lint

# Check formatting
just check-format  # or: just fmt

# Individual hook runners are also available via nixago
```

## Architecture

### Nix Configuration Structure

The configuration follows a modular design with separate concerns:

- **devenv.nix**: Main entry point, imports all modules and defines core settings
- **claude.nix**: Claude Code integration (PostToolUse hooks, MCP servers)
- **lefthook.nix**: Git hooks configuration via omnibus framework
- **files.nix**: File management configuration (currently minimal)
- **justfile**: Task runner for development workflows (changelog, releases, validation)
- **modules/flake-parts/omnibus.nix**: Omnibus framework integration module
- **devenv.yaml**: Flake inputs configuration
- **devenv.lock**: Lock file for reproducible builds
- **.envrc**: direnv configuration for automatic shell loading

### Justfile Task Runner

The repository uses **Just** (https://github.com/casey/just) as a task runner for common development workflows. Just provides fast, flexible command execution without Nix evaluation overhead.

**Why Justfile?**
- ⚡ Fast execution (no Nix evaluation overhead)
- 🔄 Easy iteration and modification
- 📝 Clear, readable syntax
- 🎯 Better for ad-hoc scripts and workflows
- 🚀 Ideal for CI/CD pipelines

**Categories of commands:**

**Setup & Validation:**
- `just setup` - Initialize development environment
- `just validate` - Run all checks (format, commits, lint, test)
- `just check-format` - Check code formatting
- `just lint` - Run linters
- `just test` - Run test suite

**Changelog Management:**
- `just changelog-preview` (or `just cl`) - Preview next changelog
- `just changelog-stats` - Show commit statistics
- `just check-commits` - Validate conventional commits
- `just changelog-export` - Export changelog in multiple formats

**Version & Release:**
- `just version` - Show current version
- `just bump-auto` - Auto-bump version based on commits
- `just bump-patch/minor/major` - Manual version bump
- `just bump-dry` - Preview version bump
- `just release-notes` - Generate release notes
- `just publish-release` - Publish to GitHub
- `just release` (or `just ship`) - Complete release workflow

**Git Operations:**
- `just status` (or `just s`) - Show enhanced git status
- `just log` - Show conventional commit log
- `just commit` (or `just c`) - Interactive commit helper
- `just examples` - Show commit message examples

**Development Helpers:**
- `just fmt` - Format all code
- `just clean` - Remove generated files
- `just update` - Update dependencies
- `just info` - Show environment information
- `just ci` - Run CI checks
- `just pre-release` - Pre-release checklist

**View all commands:**
```bash
just  # or: just --list
```

**Command dependencies:**
Commands can depend on each other. For example:
- `just validate` runs: `check-format`, `check-commits`, `lint`, `test`
- `just release` runs: `bump-auto`, then `publish-release`
- `just bump-auto` first runs: `validate`

### Claude Code Integration

Claude Code is fully integrated via `claude.nix`:

**Features:**
- `claude.code.enable = true`: Activates Claude Code support
- **PostToolUse Hook**: Automatically runs `lefthook run` after Edit/MultiEdit/Write operations
- **MCP Servers**: Two Model Context Protocol servers configured:
  - `devenv`: Local devenv MCP server for devenv-specific queries
  - `nixos`: NixOS package/option search via github:utensils/mcp-nixos

**Hook Behavior:**
The PostToolUse hook runs `cd "$DEVENV_ROOT" && lefthook run` whenever Claude Code edits, multi-edits, or writes files. This ensures:
- Nix files are formatted with nixfmt
- Shell scripts are formatted with shfmt
- Code quality is maintained automatically

### Git Hooks (Lefthook)

Git hooks are managed via **lefthook** through the omnibus framework integration in `lefthook.nix`.

**Architecture:**
The lefthook configuration uses a functional map-based approach:

```nix
generators = [
  { name = "lefthook"; gen = (config.omnibus.ops.mkNixago ...) ... }
  { name = "conform"; gen = (config.omnibus.ops.mkNixago ...) }
]
generatedHooks = map (g: g.gen) generators;
```

This design allows easy extension by adding new generators to the list.

**Active Hooks:**
- **pre-commit**: nixfmt, shfmt, hunspell, typos
- **commit-msg**: conform (commit message linting)

**Configuration Files:**
- `lefthook.yml`: Generated hook configuration (symlinked to Nix store)
- `.conform.yaml`: Conform commit message policy

### Omnibus Framework Integration

The repository integrates the **omnibus** framework for advanced configuration management.

**Module Location:** `modules/flake-parts/omnibus.nix`

**Purpose:**
- Provides flexible configuration system with load extenders
- Enables nixago-based configuration file generation
- Manages lefthook and conform configurations
- Integrates git-hooks from omnibus.flake.inputs

**Configuration in devenv.nix:**
```nix
omnibus = {
  inputs = {
    inputs = {
      nixpkgs = pkgs;
      inherit (inputs.omnibus.flake.inputs) nixago;
    };
  };
};
```

### Available Packages

Core packages installed in `devenv.nix`:
- `git`: Version control
- `claude-code`: Claude Code CLI tool

Additional packages are dynamically provided by generated hooks (lefthook, conform, hunspell, typos, etc.)

### Scripts

**hello script:**
- Prints "hello from $GREET" (where GREET=devenv)
- Run with: `hello`

### Environment Variables

- **GREET**: Set to "devenv", used by hello script and enterShell message
- **DEVENV_ROOT**: Set by devenv, used in Claude Code hooks

## Code Modification Guidelines

**Modifying Nix files:**
- All `.nix` files are automatically formatted by nixfmt via lefthook
- Configuration follows devenv's modular structure with imports
- Use proper Nix formatting (nixfmt will auto-fix)

**Adding new packages:**
- Add to `packages = [ ... ]` list in `devenv.nix`
- Packages from omnibus framework are added via `lefthook.nix` generators

**Extending git hooks:**
- Add new generators to the `generators` list in `lefthook.nix`
- Each generator should follow the pattern:
  ```nix
  {
    name = "hook-name";
    gen = (config.omnibus.ops.mkNixago config-spec);
  }
  ```

**Working with omnibus:**
- Omnibus configurations are loaded via `inputs.omnibus.units.configs`
- Additional inputs can be passed via the `omnibus.inputs` option
- Load extenders provide flexible configuration composition

## Flake Inputs

Defined in `devenv.yaml`:

- **nixpkgs**: `github:cachix/devenv-nixpkgs/rolling` - Rolling release for devenv compatibility
- **nixpkgs-latest**: `github:NixOS/nixpkgs/nixpkgs-unstable` - Latest unstable for cutting-edge packages (used by lefthook.nix)
- **omnibus**: `github:tao3k/omnibus/main` - Framework for advanced configuration management

Settings:
- `allowUnfree: true`: Permits unfree packages

## Version Control & Changelog Workflow

This repository uses **Cocogitto (cog)** for automated changelog generation and version management, combined with **conform** for commit message linting.

### Conventional Commits

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. The conform hook enforces this automatically.

**Allowed commit types** (defined in `.conform.yaml`):
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring without changing functionality
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI/CD configuration changes
- `chore`: Other changes that don't modify src or test files

**Commit message format:**
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Examples:**
```bash
git commit -m "feat: add support for custom nixago configurations"
git commit -m "fix(lefthook): resolve jq parse error on shell entry"
git commit -m "docs: update CLAUDE.md with changelog workflow"
git commit -m "refactor: use map for generator configuration in lefthook.nix"
git commit -m "chore(claude): update claude integration settings"

# Or use the interactive commit helper
just commit  # or: just c
```

### Changelog Generation

The changelog is automatically generated using cocogitto and stored in `CHANGELOG.md`.

**Configuration** (in `lefthook.nix` and `cog.toml`):
- Repository: `github.com/tao3k/devenv-native`
- Changelog path: `CHANGELOG.md`
- Template: `remote` (GitHub links)
- Tag prefix: `v`
- Branch whitelist: `main`, `release/**`

**Recommended workflow (using Justfile):**
```bash
# Preview changelog for next release
just changelog-preview  # or: just cl

# Show changelog statistics
just changelog-stats

# Validate all commits
just check-commits

# Export changelog in multiple formats (Markdown, JSON, Plain text)
just changelog-export v0.1.0
```

**Direct cog commands (alternative):**
```bash
# Generate changelog for current version
cog changelog  # or: just changelog

# Generate changelog at specific tag
cog changelog --at v0.1.0  # or: just changelog-at v0.1.0

# Preview changes since last tag
cog log  # or: just log
```

### Version Bumping Workflow

Cocogitto manages semantic versioning automatically based on conventional commits.

**Recommended workflow (using Justfile):**
```bash
# Show current version
just version

# Preview version bump (dry run)
just bump-dry

# Automatic version bump (analyzes commits since last tag)
just bump-auto  # Runs validation first

# Manual version bump
just bump-major    # 1.0.0 -> 2.0.0
just bump-minor    # 1.0.0 -> 1.1.0
just bump-patch    # 1.0.0 -> 1.0.1

# Bump with pre-release
just bump-pre alpha
just bump-pre beta

# Complete release workflow (bump + publish to GitHub)
just release  # or: just ship
```

**Direct cog commands (alternative):**
```bash
# Automatic version bump
cog bump --auto

# Manual version bump
cog bump --major/--minor/--patch

# Dry run
cog bump --auto --dry-run
```

**Automated bump workflow** (configured in `cog.toml`):

1. **Pre-bump hooks**:
   - Write version to `./VERSION` file
   - Create or switch to `release/X.Y` branch (minor version branch)
   - Merge main into release branch

2. **Bump action**:
   - Update version in VERSION file
   - Generate changelog
   - Create git tag with `v` prefix (e.g., `v0.1.0`)

3. **Post-bump hooks**:
   - Push release branch with upstream tracking
   - Push version tag
   - Switch back to main
   - Merge release branch to main (no-commit, no-ff)
   - Increment to next dev version (e.g., `0.2.0-dev`)
   - Commit and push main

### Release Workflow

**Recommended workflow (using Justfile):**

```bash
# 1. Ensure you're on main branch with latest changes
git checkout main
git pull

# 2. Run pre-release checklist (validation + preview + stats)
just pre-release

# 3. Perform complete release (bump + publish to GitHub)
just release

# Or step-by-step:
# 3a. Bump version
just bump-auto  # or: just bump-patch/minor/major

# 3b. Publish to GitHub
just publish-release

# The automated workflow will:
# - Validate all commits and formatting
# - Create/update release/X.Y branch
# - Tag the release
# - Generate changelog
# - Create GitHub release with notes
# - Push to remote
# - Merge back to main
# - Set next dev version
```

**Direct approach (alternative):**
```bash
# Traditional cog workflow
git checkout main && git pull
cog log
cog bump --auto
```

**Branch strategy:**
- `main`: Development branch, always points to next dev version
- `release/X.Y`: Stable release branches (e.g., `release/0.1`)
- Tags: `vX.Y.Z` on release branches

### Checking Commit History

**Recommended (using Justfile):**
```bash
# Show recent commits in conventional format
just log  # or: just log 20

# Show enhanced git status
just status  # or: just s

# Verify commit messages
just check-commits

# Show changelog statistics
just changelog-stats

# Preview next changelog
just changelog-preview  # or: just cl
```

**Direct cog commands (alternative):**
```bash
# Show commits since last tag
cog log

# Show all commits
cog log --from-latest-tag

# Verify commit messages
cog check

# Check specific commit range
cog check --from-latest-tag
```

### Integration with Git Hooks

The conform hook automatically validates commit messages during `git commit`. If your commit message doesn't follow the conventional format, the commit will be rejected.

**Hook validation:**
- Maximum header length: 89 characters
- Required format: `<type>[optional scope]: <description>`
- Only allowed types are accepted

**Bypassing hooks** (not recommended):
```bash
git commit --no-verify -m "message"
```

### Cocogitto Configuration

The cocogitto configuration is managed via the omnibus framework in `lefthook.nix`:

```nix
{
  name = "cog";
  gen = (config.omnibus.ops.mkNixago initConfigs.nixago-cog) initConfigs.cog.default {
    data = {
      changelog = {
        path = "CHANGELOG.md";
        template = "remote";
        remote = "github.com";
        repository = "devenv-native";
        owner = "tao3k";
        authors = [
          {
            username = "gtrunsec";
            signature = "Guangtao";
          }
        ];
      };
    };
  };
}
```

The generated `cog.toml` is symlinked to the Nix store and includes pre/post bump hooks for the automated release workflow.

## MCP Servers

Two MCP servers are available for enhanced Claude Code capabilities:

1. **devenv** (`devenv mcp`):
   - Provides devenv-specific context
   - Accesses DEVENV_ROOT environment variable

2. **nixos** (`nix run github:utensils/mcp-nixos`):
   - Search NixOS packages and options
   - Query Home Manager and nix-darwin configurations
   - Access nixpkgs package versions and flakes
