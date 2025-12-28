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
# Git hooks are managed via lefthook (omnibus framework)
# Hooks run automatically on commit, triggered manually with:
lefthook run

# Individual hook runners are also available via nixago
```

## Architecture

### Nix Configuration Structure

The configuration follows a modular design with separate concerns:

- **devenv.nix**: Main entry point, imports all modules and defines core settings
- **claude.nix**: Claude Code integration (PostToolUse hooks, MCP servers)
- **lefthook.nix**: Git hooks configuration via omnibus framework
- **files.nix**: File management configuration (currently minimal)
- **modules/flake-parts/omnibus.nix**: Omnibus framework integration module
- **devenv.yaml**: Flake inputs configuration
- **devenv.lock**: Lock file for reproducible builds
- **.envrc**: direnv configuration for automatic shell loading

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

## MCP Servers

Two MCP servers are available for enhanced Claude Code capabilities:

1. **devenv** (`devenv mcp`):
   - Provides devenv-specific context
   - Accesses DEVENV_ROOT environment variable

2. **nixos** (`nix run github:utensils/mcp-nixos`):
   - Search NixOS packages and options
   - Query Home Manager and nix-darwin configurations
   - Access nixpkgs package versions and flakes
