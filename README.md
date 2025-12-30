# omni-devenv-fusion

> Orchestrator-Worker workflow with devenv, Nix, and Claude Code

A development environment showcasing AI-assisted software development lifecycle (SDLC) with the Orchestrator pattern.

## Quick Start

```bash
# Clone and enter
git clone https://github.com/tao3k/omni-devenv-fusion.git
cd omni-devenv-fusion

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
omni-devenv-fusion/
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

### MCP Server

```bash
just run               # Run MCP server
just debug             # Debug with MCP Inspector
just test-mcp          # Syntax check + startup test
just test_basic        # Basic MCP tests
just test_workflow     # Workflow integration tests
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

### MCP Server Commands

```bash
# Run the MCP orchestrator server
just run

# Debug with MCP Inspector
just debug

# Test MCP server functionality
just test-mcp       # Syntax check + server startup
just test_basic     # Run basic MCP tests
just test_workflow  # Run workflow integration tests
```

### Testing

```bash
# Run basic tests (MCP initialization, tools, context)
uv run python tests/test_basic.py

# Run full workflow tests (consult_specialist, personas)
uv run python tests/workflows.py
```

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

Secrets are managed via **secretspec**, a tool for secure credential handling. Multiple providers are supported.

### Supported Providers

| Provider | Description | Use Case |
|----------|-------------|----------|
| `keyring` | System keyring (macOS Keychain, KWallet) | Local development |
| `1password` | 1Password | Team sharing |
| `lastpass` | LastPass | Team sharing |
| `dotenv` | .env file | Local development |
| `env` | Environment variables | CI/CD |

### Configuration

**Provider Selection** (in `devenv.yaml`):

```yaml
secretspec:
  enable: true
  provider: keyring  # or: onepassword, lastpass, dotenv, env
  profile: development
```

**Secret Definitions** (in `secretspec.toml`):

```toml
[project]
name = "omni-devenv-fusion"
revision = "1.0"

[profiles.default]
MINIMAX_API_KEY = { description = "API key for MiniMax", required = true }

[profiles.development]
# Inherits from default, override as needed
```

### Setup Commands

```bash
# Check secret status
just secrets-check

# View secrets info
just secrets-info

# Set a secret (interactive)
just secrets-set-minimax

# Or use secretspec directly
secretspec set MINIMAX_API_KEY --value "your-api-key"
secretspec set MINIMAX_API_KEY --profile development --value "dev-key"

# Get secret value (masked)
secretspec get MINIMAX_API_KEY
```

### 1Password Setup (Optional)

If using 1Password as provider:

```bash
# 1. Install 1Password CLI (handled by devenv)
# 2. Sign in
op signin

# 3. Add secret to 1Password
#    Run: just secrets-set-minimax
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

- [devenv.sh](https://devenv.sh) - Development environments with Nix
- [Nix Manual](https://nixos.org/manual/nix/stable/) - Nix package manager
- [just](https://github.com/casey/just) - Command runner
- [Conventional Commits](https://www.conventionalcommits.org/) - Commit message specification
- [cocogitto](https://github.com/cocogitto/cocogitto) - Changelog and version management
- [lefthook](https://github.com/evilmartians/lefthook) - Git hooks manager
- [omnibus](https://github.com/tao3k/omnibus) - Configuration framework
- [secretspec](https://github.com/tao3k/secretspec) - Secret management
- [Claude Code](https://claude.com/claude-code) - AI coding assistant

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following conventional commits
4. Run `just validate` to ensure checks pass
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

Built with modern tools that empower AI-assisted software development:

- **Anthropic Claude Code** - AI-powered coding assistant with MCP support
- **devenv** - Reproducible development environments
- **Nix ecosystem** - Declarative package management
- **omnibus framework** - Advanced configuration management
- **cocogitto** - Automated changelog and versioning
- **lefthook** - Fast and powerful Git hooks

Special thanks to the maintainers of these projects for enabling the AI-SDLC workflow.

---

Built with ❤️ using devenv, Nix, and Claude Code
