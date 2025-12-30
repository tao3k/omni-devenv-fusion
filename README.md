# omni-devenv-fusion

> Exploring AI-assisted coding workflows with devenv, Nix ecosystem, and modern SDLC standards

A showcase repository demonstrating best practices for AI-powered development environments using:
- **devenv** for reproducible development shells
- **Nix** for declarative package management
- **Claude Code** integration with MCP servers
- **Conventional Commits** and automated changelog generation
- **Modern SDLC** workflows with git hooks and validation

## Quick Start

```bash
# Clone the repository
git clone https://github.com/tao3k/omni-devenv-fusion.git
cd omni-devenv-fusion

# Setup (direnv will auto-load the environment)
just setup

# See all available commands
just

# Start developing with confidence
just validate  # Run all checks
just cl        # Preview changelog
```

## Features

### 🤖 AI-Powered Development

- **Claude Code Integration**: Native support for Claude Code with PostToolUse hooks
- **MCP Servers**:
  - `devenv` - Local devenv context and commands
  - `nixos` - NixOS packages, options, and flake search
- **Automated Quality**: Code formatting and linting on every edit

### 📦 Reproducible Environments

- **devenv**: Declarative development environments with Nix
- **direnv**: Automatic environment loading
- **Cached Profiles**: Fast environment activation using `.direnv` cache
- **Cross-platform**: Works on macOS and Linux

### 🔄 Modern SDLC Workflow

- **Conventional Commits**: Enforced via conform hook
- **Automated Changelog**: Generated with cocogitto
- **Semantic Versioning**: Automatic version bumping based on commits
- **Git Hooks**: Managed by lefthook via omnibus framework
- **GitHub Releases**: Automated release notes and publishing

### ⚡ Fast Task Runner

- **Justfile**: Lightning-fast command execution (no Nix eval overhead)
- **40+ Commands**: Organized into logical categories
- **Interactive Helpers**: Guided commit creation and validation
- **CI/CD Ready**: Pre-configured validation and release workflows

## Architecture

### Configuration Files

```
omni-devenv-fusion/
├── devenv.nix              # Main devenv configuration
├── claude.nix              # Claude Code integration
├── lefthook.nix            # Git hooks via omnibus
├── justfile                # Task runner commands
├── cog.toml                # Cocogitto configuration (generated)
├── .conform.yaml           # Commit message validation (generated)
├── lefthook.yml            # Git hook definitions (generated)
└── modules/
    └── flake-parts/
        └── omnibus.nix     # Omnibus framework integration
```

### Key Technologies

| Technology | Purpose | Configuration |
|------------|---------|---------------|
| **devenv** | Development environment | `devenv.nix`, `devenv.yaml` |
| **direnv** | Auto-load environment | `.envrc` |
| **Claude Code** | AI coding assistant | `claude.nix` |
| **lefthook** | Git hook manager | `lefthook.nix`, `lefthook.yml` |
| **cocogitto** | Changelog generator | `cog.toml` |
| **conform** | Commit validation | `.conform.yaml` |
| **just** | Task runner | `justfile` |
| **omnibus** | Config framework | `modules/flake-parts/omnibus.nix` |

## Development Workflow

### Daily Development

```bash
# Make changes to code
# Git hooks automatically validate on commit

# Preview what will be in the next release
just changelog-preview

# Interactive commit with guidance
just commit

# Or commit directly
git commit -m "feat(api): add new endpoint"
```

### Release Process

```bash
# 1. Validate everything
just pre-release

# 2. Bump version and release (one command!)
just release

# Or step-by-step:
just bump-auto          # Analyze commits and bump version
just publish-release    # Create GitHub release with notes
```

### Common Tasks

```bash
# Validation
just validate           # Run all checks (format, commits, lint, test)
just check-format       # Check code formatting only
just check-commits      # Validate commit messages

# Changelog
just cl                 # Preview next changelog
just changelog-stats    # Show commit statistics
just changelog-export   # Export in multiple formats

# Version Management
just version            # Show current version
just bump-dry           # Preview version bump
just bump-patch         # Bump patch version (0.0.X)

# Development
just fmt                # Format all code
just test               # Run test suite
just info               # Show environment info
```

## Conventional Commits

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style (formatting, missing semicolons, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Other changes

### Examples

```bash
# Simple feature
git commit -m "feat: add justfile workflow"

# With scope
git commit -m "feat(claude): integrate MCP servers"

# Breaking change
git commit -m "feat(api)!: redesign configuration API

BREAKING CHANGE: Configuration moved from config.omnibus to omnibus.config"

# Or use interactive helper
just commit
```

## Claude Code Integration

### PostToolUse Hooks

Automatically runs code quality checks after Claude Code edits files:

```nix
claude.code.hooks = {
  PostToolUse = {
    command = ''
      bash -c 'cd "$DEVENV_ROOT" &&
      source "$(ls -t .direnv/devenv-profile*.rc 2>/dev/null | head -1)" &&
      lefthook run pre-commit'
    '';
    matcher = "^(Edit|MultiEdit|Write)$";
  };
};
```

### MCP Servers

Two Model Context Protocol servers provide enhanced context:

**devenv MCP**: Access devenv-specific information
```bash
devenv mcp
```

**nixos MCP**: Search NixOS packages, options, and flakes
```bash
nix run github:utensils/mcp-nixos
```

## Git Hooks

Managed by lefthook via the omnibus framework:

**Pre-commit hooks:**
- `nixfmt` - Format Nix files
- `shfmt` - Format shell scripts
- `hunspell` - Spell checking
- `typos` - Typo detection

**Commit-msg hook:**
- `conform` - Validate conventional commits

All hooks are configured using a functional map-based approach in `lefthook.nix`.

## Omnibus Framework

The repository uses the [omnibus framework](https://github.com/tao3k/omnibus) for advanced configuration management:

- Flexible configuration system with load extenders
- Nixago-based configuration file generation
- Integrated git-hooks from omnibus inputs
- Modular and composable configurations

## Installation

### Prerequisites

- [Nix](https://nixos.org/download.html) with flakes enabled
- [direnv](https://direnv.net/) (optional but recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/tao3k/omni-devenv-fusion.git
cd omni-devenv-fusion

# Allow direnv (if installed)
direnv allow

# Or enter devenv shell manually
devenv shell

# Verify setup
just info
```

**Note:** 1Password CLI is automatically installed via devenv (`pkgs._1password-cli`).

### Secret Management

Secrets are managed via **secretspec** with **1Password** as the provider. This provides secure, encrypted storage for sensitive credentials like API keys.

#### Prerequisites

1. **1Password CLI** is automatically installed via devenv when entering the shell.

2. **Sign in to 1Password**:
   ```bash
   op signin
   ```

#### Available Secrets

| Secret | Profile | Description |
|--------|---------|-------------|
| `MINIMAX_API_KEY` | default | API key for MiniMax API access |

#### Managing Secrets

```bash
# Check secret status
secretspec check --profile development

# Set a secret value
secretspec set MINIMAX_API_KEY --value "your-api-key"

# Set profile-specific value
secretspec set MINIMAX_API_KEY --profile development --value "your-dev-key"

# View secret value (masked)
secretspec get MINIMAX_API_KEY
```

#### Justfile Commands for Secrets

```bash
# Check all secrets status
just secrets-check

# Set MINIMAX_API_KEY
just secrets-set-minimax

# View secrets info
just secrets-info
```

#### Configuration

The secretspec configuration is defined in `secretspec.toml`:

```toml
[project]
name = "omni-devenv-fusion"
revision = "1.0"

[profiles.default]
MINIMAX_API_KEY = { description = "API key for MINIMAX", required = true }

[profiles.development]
# Inherits from default, override secrets as needed
```

The provider is configured in `devenv.yaml`:

```yaml
secretspec:
  enable: true
  provider: onepassword  # keyring, dotenv, env, 1password, lastpass
  profile: development
```

## Project Structure

```
omni-devenv-fusion/
├── .claude/                # Claude Code configuration
├── .direnv/                # Cached devenv profiles
├── modules/
│   └── flake-parts/
│       └── omnibus.nix     # Omnibus integration module
├── claude.nix              # Claude Code integration
├── devenv.nix              # Main devenv configuration
├── devenv.yaml             # Flake inputs
├── files.nix               # File management
├── lefthook.nix            # Git hooks configuration
├── justfile                # Task runner
├── CLAUDE.md               # Detailed documentation for Claude Code
├── README.md               # This file
└── CHANGELOG.md            # Generated changelog
```

## CI/CD

The repository includes configurations for automated workflows:

```bash
# Run what CI would run locally
just ci

# Pre-release validation
just pre-release

# Complete release
just release
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following conventional commits
4. Run `just validate` to ensure all checks pass
5. Submit a pull request

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive guide for Claude Code
- **[CHANGELOG.md](CHANGELOG.md)** - Generated changelog
- `just examples` - Commit message examples
- `just docs` - Documentation index

## License

[Add your license here]

## Resources

- [devenv Documentation](https://devenv.sh)
- [Nix Manual](https://nixos.org/manual/nix/stable/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Cocogitto](https://github.com/cocogitto/cocogitto)
- [just Manual](https://github.com/casey/just)
- [Omnibus Framework](https://github.com/tao3k/omnibus)

## Acknowledgments

This project demonstrates modern development workflows by integrating:
- **Anthropic Claude Code** - AI-powered coding assistant
- **devenv** - Reproducible development environments
- **Nix ecosystem** - Declarative package management
- **Omnibus framework** - Advanced configuration management

---

**Built with ❤️ using devenv, Nix, and Claude Code**
