# devenv-native

> AI-SDLC Lab: Orchestrator-Worker workflow with devenv, Nix, and Claude Code

A development environment showcasing AI-assisted software development lifecycle (SDLC) with the Orchestrator pattern.

## Quick Start

```bash
# Clone and enter
git clone https://github.com/GTrunSec/devenv-native.git
cd devenv-native

# Setup (direnv auto-loads the environment)
just setup

# View all commands
just

# Validate everything
just validate
```

## Key Features

### 🤖 Orchestrator-Worker Pattern

Claude Code acts as the **Lead Architect & Orchestrator**, delegating complex tasks to specialized experts via MCP:

- **`architect`**: High-level design, refactoring strategies
- **`platform_expert`**: Nix/OS configuration, infrastructure
- **`devops_mlops`**: CI/CD pipelines, build workflows
- **`sre`**: Reliability, observability, security

```bash
# Example: Consult multiple experts for a complex task
just agent-commit "feat" "" "add redis service"
# Delegates to platform_expert for devenv config,
# devops_mlops for CI/CD, sre for health checks
```

### ⚡ Agent-Friendly Commands

All commands support non-interactive execution for AI agents:

| Command | Description |
|---------|-------------|
| `just agent-commit <type> "" <msg>` | Non-interactive commit |
| `just agent-validate` | Run all checks |
| `just agent-fmt` | Apply formatting fixes |
| `just agent-bump [auto\|patch\|minor\|major]` | Version bump |
| `just agent-release` | Complete release workflow |

### 🏥 SRE Health Checks

Built-in health monitoring with machine-parseable JSON output:

```bash
# Human-readable
just health

# Machine-parseable (for CI/AI)
JUST_JSON=true just health-report
# {"component":"git","branch":"main",...}
```

Available checks:
- `health-git` - Repository status
- `health-nix` - Nix environment
- `health-devenv` - Devenv configuration
- `health-secrets` - Secret availability
- `health-api-keys` - API key validation

### 📦 Reproducible Environments

- **devenv**: Declarative development shells with Nix
- **direnv**: Automatic environment loading
- **omnibus**: Modular configuration framework
- **flake-parts**: Composable Nix modules

### 🔄 Modern SDLC

- **Conventional Commits**: Enforced via conform
- **Automated Changelog**: Generated with cocogitto
- **Semantic Versioning**: Auto-bump based on commits
- **Git Hooks**: lefthook + omnibus framework

## Architecture

```
devenv-native/
├── devenv.nix              # Main devenv configuration
├── devenv.yaml             # Flake inputs
├── justfile                # Task runner (40+ commands)
├── CLAUDE.md               # Orchestrator instructions
├── modules/
│   ├── claude.nix          # Claude Code + MCP servers
│   ├── lefthook.nix        # Git hooks (omnibus)
│   ├── python.nix          # Python environment
│   └── flake-parts/
│       └── omnibus.nix     # Omnibus framework
└── mcp-server/
    └── orchestrator.py     # Expert consultation server
```

## Available Commands

### Validation & Quality

```bash
just validate      # Run all checks (fmt, lint, test)
just check-format  # Check formatting only
just check-commits # Validate commit messages
just lint          # Run linters
just fmt           # Format code
just test          # Run tests
```

### Changelog & Version

```bash
just changelog-preview  # Preview next release
just changelog-stats    # Commit statistics
just version            # Show current version
just bump-auto          # Auto-bump version
just bump-patch         # Bump patch (0.0.X)
```

### Git Operations

```bash
just status            # Repository status
just log               # Recent commits
just agent-commit      # Non-interactive commit
just commit            # Interactive commit (human)
```

### Health & Diagnostics

```bash
just health            # Full health check
just health-report     # JSON report (for AI/CI)
just secrets-check     # Secret availability
just info              # Environment info
```

### Release

```bash
just pre-release       # Pre-release checklist
just release           # Complete release
just publish-release   # Publish to GitHub
```

## Claude Code Integration

### PostToolUse Hook

Claude Code automatically runs quality checks after edits:

```nix
claude.code.hooks = {
  PostToolUse = {
    command = "lefthook run pre-commit";
    matcher = "^(Edit|MultiEdit|Write)$";
  };
};
```

### MCP Servers

- **devenv**: Local devenv context
- **nixos**: NixOS package/option search
- **orchestrator**: Expert consultation (architect, platform_expert, devops_mlops, sre)

### Orchestrator Workflow

```python
# MCP orchestrator.py provides expert consultation
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orchestrator-tools")

@mcp.tool()
def consult_specialist(role: str, query: str) -> str:
    """Consult AI expert for domain-specific guidance"""
    # Returns expert opinion based on role
```

## Conventional Commits

All commits follow the specification:

```
<type>: <description>

Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore
```

### Examples

```bash
# Agent (automated)
just agent-commit "feat" "" "add sre health checks"

# Human (interactive)
just commit
# Guides through type/scope/body/breaking change selection
```

## Secret Management

Secrets managed via **secretspec** with 1Password:

```bash
# Set API key
secretspec set MINIMAX_API_KEY --value "your-key"

# Check status
just secrets-check
```

## Development

```bash
# Setup
just setup

# Iterate
just validate  # Before committing
just agent-commit "fix" "" "fix bug"

# Release
just pre-release
just release
```

## Resources

- [devenv.sh](https://devenv.sh)
- [just](https://github.com/casey/just)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [cocogitto](https://github.com/cocogitto/cocogitto)
- [omnibus](https://github.com/tao3k/omnibus)

---

Built with devenv, Nix, and Claude Code
