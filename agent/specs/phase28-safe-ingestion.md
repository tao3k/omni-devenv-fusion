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

| Version | Date       | Changes      |
| ------- | ---------- | ------------ |
| 1.0.0   | 2026-01-06 | Initial plan |
