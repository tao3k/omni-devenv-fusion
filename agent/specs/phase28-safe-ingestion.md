# Phase 28: Safe Ingestion / Immune System

> **Status**: PLANNED
> **Date**: 2026-01-06
> **Owner**: System Architecture

## Overview

Phase 28 introduces **Safe Ingestion** - a security layer for downloading and executing third-party skills from Git repositories.

When a skill is installed via JIT or `omni skill install`, the system now:

1. **Scans** the code for malicious patterns
2. **Validates** the manifest for dangerous permissions
3. **Sandboxes** the skill in an isolated environment
4. **Alerts** the user if suspicious behavior is detected

## Problem Statement

```
User: omni skill install https://github.com/random-user/malicious-skill

Old Behavior:
→ Code downloaded and executed immediately
→ No security checks
→ Full system access granted

New Behavior:
→ Code scanned for dangerous patterns
→ Manifest validated for permissions
→ User warned if suspicious
→ Optional sandboxed execution
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Phase 28: Safe Ingestion / Immune System            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────────────────────────┐  │
│  │ Git Download    │   │ Security Scanner                    │  │
│  │                 │   │                                     │  │
│  │ • Clone repo    │──▶│ • Pattern detection                 │  │
│  │ • Sparse checkout│  │ • AST analysis                      │  │
│  │ • Extract files │   │ • Dependency check                  │  │
│  └────────┬────────┘   └──────────────┬──────────────────────┘  │
│           │                           │                         │
│           ▼                           ▼                         │
│  ┌─────────────────┐   ┌─────────────────────────────────────┐  │
│  │ Manifest        │   │ Immune System                       │  │
│  │ Validator       │   │                                     │  │
│  │                 │   │ • Suspicious permission flags       │  │
│  │ • Schema check  │──▶│ • Network access patterns           │  │
│  │ • Permission    │   │ • File system access patterns       │  │
│  │   audit         │   │ • Shell command execution           │  │
│  └────────┬────────┘   └──────────────┬──────────────────────┘  │
│           │                           │                         │
│           ▼                           ▼                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Decision Engine                        │  │
│  │                                                           │  │
│  │  SAFE      → Allow, load normally                        │  │
│  │  WARN      → Allow with user warning                     │  │
│  │  SANDBOX   → Run in restricted environment               │  │
│  │  BLOCK     → Reject, do not load                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Security Checks

### 1. Code Pattern Detection

**Dangerous Patterns:**

```python
# Shell command injection
os.system(user_input)
subprocess shell=True
eval(user_input)
exec(user_input)

# File system access
open("/etc/passwd")
path traversal: "../"

# Network access
socket.connect()
requests to suspicious domains

# Code execution
__import__()
getattr(os, "system")
```

**Scoring System:**

- Critical (+50): Shell injection, eval/exec
- High (+30): File write, network call
- Medium (+10): File read, subprocess
- Low (+5): Any system access

**Thresholds:**

- SAFE: Score < 10
- WARN: 10 <= Score < 30
- BLOCK: Score >= 30

### 2. Manifest Permission Audit

**Suspicious Permissions:**

```json
{
  "permissions": {
    "network": true, // Warn if external skill
    "filesystem": "write", // Block unless trusted
    "shell": true, // Warn
    "exec": true // Block
  }
}
```

### 3. Dependency Security

- Check for known vulnerable packages
- Warn about outdated dependencies
- Flag known malicious packages

## Components

### Security Scanner

**File**: `agent/core/security/scanner.py`

```python
class SecurityScanner:
    """Scan skill code for security issues."""

    def scan(self, skill_path: Path) -> SecurityReport:
        """
        Scan a skill for security issues.

        Returns:
            SecurityReport with score and findings
        """

    def detect_patterns(self, code: str) -> list[Finding]:
        """Detect dangerous code patterns."""

    def check_dependencies(self, manifest: dict) -> list[str]:
        """Check for vulnerable dependencies."""
```

### Manifest Validator

**File**: `agent/core/security/manifest_validator.py`

```python
class ManifestValidator:
    """Validate skill manifest for security."""

    def validate(self, manifest: dict) -> ValidationResult:
        """
        Validate manifest permissions.

        Returns:
            ValidationResult with permission flags
        """
```

### Immune System

**File**: `agent/core/security/immune_system.py`

```python
class ImmuneSystem:
    """Central security decision engine."""

    def assess(self, security_report: SecurityReport) -> Decision:
        """
        Make security decision based on report.

        Returns:
            Decision: SAFE, WARN, SANDBOX, or BLOCK
        """
```

## Integration with Existing Code

### Updated Installer

```python
# In installer.py - after cloning
def install_remote_skill(url: str) -> InstallResult:
    # ... existing clone code ...

    # Phase 28: Security scan
    scanner = SecurityScanner()
    report = scanner.scan(skill_path)

    immune = ImmuneSystem()
    decision = immune.assess(report)

    if decision == ImmuneSystem.BLOCK:
        return InstallResult(
            success=False,
            error="Skill blocked due to security concerns",
            report=report
        )

    # Continue with installation
    # ...
```

### Updated JIT Install

```python
# In skill_registry.py - jit_install_skill
def jit_install_skill(skill_id: str) -> dict:
    # ... existing discovery code ...

    # Phase 28: Security scan before loading
    scanner = SecurityScanner()
    report = scanner.scan(skill_path)

    if report.score >= ImmuneSystem.BLOCK_THRESHOLD:
        return {
            "success": False,
            "error": "Skill blocked for security",
            "report": report
        }

    # ... continue with load ...
```

## CLI Integration

```bash
# Install with security check (default)
omni skill install https://github.com/omni-dev/skill-docker
→ Scans code, validates manifest, reports security status

# Install without security check (trusted source)
omni skill install https://github.com/omni-dev/skill-docker --trust
→ Skips security scan

# View security report
omni skill info docker-ops --security
→ Shows detailed security analysis
```

## Configuration

```yaml
# assets/settings.yaml

security:
  # Enable/disable security scanning
  enabled: true

  # Thresholds (0-100)
  block_threshold: 30
  warn_threshold: 10

  # Trusted sources (skip scan)
  trusted_sources:
    - "github.com/omni-dev"
    - "github.com/trusted-org"

  # Sandbox configuration
  sandbox:
    enabled: true
    timeout_seconds: 30
    memory_limit_mb: 128
```

## Future Enhancements

1. **Sandboxing**: Docker-based or namespace-based isolation
2. **Community Ratings**: User-reported security concerns
3. **Automated Updates**: Re-scan skills on dependency updates
4. **Audit Logging**: Log all security decisions

## Test Coverage

| Test File                            | Tests                           |
| ------------------------------------ | ------------------------------- |
| `test_phase28_security_scanner.py`   | Pattern detection, AST analysis |
| `test_phase28_manifest_validator.py` | Permission validation           |
| `test_phase28_immune_system.py`      | Decision engine                 |
| `test_phase28_integration.py`        | Full workflow                   |

## Changelog

| Version | Date       | Changes                          |
| ------- | ---------- | -------------------------------- |
| 1.1.0   | 2026-01-06 | Add Subprocess/Shim Architecture |
| 1.0.0   | 2026-01-06 | Initial plan                     |

---

# Appendix A: Subprocess/Shim Architecture (Phase 28.1)

> **Philosophy**: "Don't import what you can't isolate."
>
> For skills with heavy/conflicting dependencies (e.g., `crawl4ai` with `pydantic v1` vs Omni's `pydantic v2`), use **subprocess isolation** instead of library import.

## Problem: Dependency Hell

```
Omni Agent: langchain → pydantic v2
Skill: crawl4ai → pydantic v1  # CONFLICT!
```

If we import `crawl4ai` directly into the Agent's memory:

- Version conflicts crash the Agent
- Memory leaks in the skill affect the entire system
- No user control over skill dependencies

## Solution: Shim Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Omni Agent (Main Process)                    │
│                                                                  │
│  ┌─────────────┐     subprocess     ┌─────────────────────┐    │
│  │ tools.py    │ ──────────────────▶ │ .venv/bin/python   │    │
│  │ (Shim)      │                     │                     │    │
│  │             │                     │ implementation.py   │    │
│  └─────────────┘                     │ (Heavy deps here)   │    │
│                                        └─────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Skill Directory Structure

```
assets/skills/crawl4ai/
├── .venv/                      # Isolated Python environment
│   └── bin/python
├── manifest.json               # Execution mode declaration
├── pyproject.toml              # Skill's own dependencies
├── implementation.py           # Real business logic (heavy imports)
└── tools.py                    # Lightweight shim (no heavy imports)

```

## Manifest Configuration

```json
{
  "name": "crawl4ai",
  "version": "1.0.0",
  "execution_mode": "subprocess",
  "entry_point": "implementation.py",
  "permissions": {
    "network": true,
    "filesystem": "read"
  }
}
```

## Shim Pattern: tools.py

**Key principle**: This file runs in Omni's main process. It MUST NOT import heavy dependencies.
Uses `uv run` for cross-platform, self-healing environment management.

```python
# assets/skills/crawl4ai/tools.py
import subprocess
import json
import os
from pathlib import Path
from agent.skills.decorators import skill_command

# Skill directory (computed at import time)
SKILL_DIR = Path(__file__).parent
IMPLEMENTATION_SCRIPT = "implementation.py"  # Relative path for uv run

def _run_isolated(command: str, **kwargs) -> str:
    """Execute command in skill's isolated Python environment using uv run.

    uv run automatically:
    - Discovers the virtual environment in SKILL_DIR
    - Creates .venv if missing (self-healing)
    - Handles cross-platform paths (Windows/Linux/Mac)
    """

    # Build command: uv run python implementation.py <command> <json_args>
    cmd = [
        "uv", "run",
        "-q",  # Quiet mode, reduce uv's own output
        "python",
        IMPLEMENTATION_SCRIPT,
        command,
        json.dumps(kwargs),
    ]

    try:
        # Critical: cwd=SKILL_DIR tells uv to use Skill's environment
        result = subprocess.run(
            cmd,
            cwd=SKILL_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")}
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        return f"Error (Exit {e.returncode}):\n{e.stderr}"

@skill_command(name="crawl_webpage", description="Crawl a URL using crawl4ai.")
def crawl_webpage(url: str, fit_markdown: bool = True) -> str:
    """Crawl webpage - delegates to isolated subprocess."""
    return _run_isolated("crawl", url=url, fit_markdown=fit_markdown)

@skill_command(name="crawl_sitemap", description="Extract links from sitemap.")
def crawl_sitemap(url: str, max_urls: int = 10) -> str:
    """Extract sitemap - delegates to isolated subprocess."""
    return _run_isolated("sitemap", url=url, max_urls=max_urls)
```

## Implementation: implementation.py

**Key principle**: This file runs in the subprocess. It CAN import anything.

```python
# assets/skills/crawl4ai/implementation.py
import sys
import json
import asyncio
from crawl4ai import AsyncWebCrawler

async def crawl(url, fit_markdown):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url)
        return result.markdown.fit_markdown if fit_markdown else result.markdown.raw

async def sitemap(url, max_urls):
    # Implementation here
    pass

def main():
    command = sys.argv[1]
    args = json.loads(sys.argv[2])

    if command == "crawl":
        result = asyncio.run(crawl(args["url"], args.get("fit_markdown", True)))
        print(result)
    elif command == "sitemap":
        result = asyncio.run(sitemap(args["url"], args.get("max_urls", 10)))
        print(json.dumps(result))
    else:
        raise ValueError(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
```

## User Setup Workflow

```bash
# User sees error when trying to use crawl4ai
@omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
# → Error: Skill environment not found

# User sets up isolated environment
cd assets/skills/crawl4ai
uv venv
uv pip install -r requirements.txt  # Installs crawl4ai, playwright, etc.

# Now it works
@omni("crawl4ai.crawl_webpage", {"url": "https://example.com"})
# → Calls .venv/bin/python implementation.py crawl '{"url": "..."}'
```

## Comparison: Library Mode vs Subprocess Mode

| Aspect            | Library Mode      | Subprocess Mode (Shim) |
| ----------------- | ----------------- | ---------------------- |
| Dependencies      | Shared with Agent | Isolated in .venv      |
| Version Conflicts | High risk         | Zero risk              |
| Crash Impact      | Crashes Agent     | Isolated subprocess    |
| User Control      | None              | Full (uv pip install)  |
| Startup Time      | Fast (import)     | Slower (process spawn) |
| Memory Usage      | Shared            | Extra process overhead |

## When to Use Each Mode

### Use Library Mode (Default) for:

- Skills with minimal dependencies
- Skills that Omni already supports (git, filesystem)
- Performance-critical operations

### Use Subprocess Mode for:

- Skills with heavy/conflicting dependencies (crawl4ai, playwright)
- Skills that might crash (untrusted code)
- Skills requiring specific Python versions

## Implementation in Skill Manager

```python
# agent/core/skill_manager.py

def _execute_tool(self, skill: Skill, tool_name: str, args: dict) -> str:
    if skill.execution_mode == "subprocess":
        return self._execute_in_subprocess(skill, tool_name, args)
    else:
        return self._execute_in_process(skill, tool_name, args)

def _execute_in_subprocess(self, skill: Skill, tool_name: str, args: dict) -> str:
    """Execute via subprocess using uv run for cross-platform isolation."""
    entry_point = skill.manifest.get("entry_point", "implementation.py")
    skill_dir = skill.path.parent  # skill.path is tools.py

    # Build uv run command
    cmd = [
        "uv", "run",
        "-q",  # Quiet mode
        "python",
        entry_point,
        tool_name,
        json.dumps(args),
    ]

    result = subprocess.run(
        cmd,
        cwd=skill_dir,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    return result.stdout.strip()
```
