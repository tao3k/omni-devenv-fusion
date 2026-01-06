# Version Control Strategy

> Monorepo version management with `hatch-vcs` + Justfile automation.

## Overview

This project uses a **hybrid versioning strategy** optimized for Python monorepos with uv workspace:

| Component                | Strategy             | Configuration       |
| ------------------------ | -------------------- | ------------------- |
| **Root** (meta-package)  | Dynamic from Git Tag | `hatch-vcs`         |
| **Agent** (sub-package)  | Static version       | `version = "x.y.z"` |
| **Common** (sub-package) | Static version       | `version = "x.y.z"` |

## Version Management Commands

### Automated Bump (Recommended)

```bash
# Auto-detect version type based on conventional commits
just bump-auto

# Explicit version type
just bump-patch  # 0.2.0 -> 0.2.1
just bump-minor  # 0.2.0 -> 0.3.0
just bump-major  # 0.2.0 -> 1.0.0
```

### Manual Version Set

```bash
# Set exact version across all packages
just bump-set 0.3.0
```

### Version Sync

```bash
# Sync version from VERSION file to all sub-packages
just _sync-versions
```

## Release Workflow

```
1. Bump Version
   just bump-auto   # or just bump-set 0.3.0

2. Commit Changes
   git add -A && git commit -m "chore: bump version to 0.3.0"

3. Tag Release
   git tag v0.3.0

4. Push
   git push origin main v0.3.0
```

## Version File

The `VERSION` file stores the source of truth for versions:

```bash
# Current version
cat VERSION
# Output: 0.3.0

# Check current versions across packages
grep "^version = " pyproject.toml packages/python/*/pyproject.toml
```

## Configuration Details

### Root `pyproject.toml`

```toml
[project]
name = "omni-dev-fusion"
dynamic = ["version"]  # Version from hatch-vcs

[build-system]
requires = ["hatchling", "hatch-vcs"]

[tool.hatch.version]
source = "vcs"  # Reads from Git Tag
```

### Sub-packages `pyproject.toml`

```toml
[project]
name = "omni-dev-fusion-agent"
version = "0.3.0"  # Static version (synced from VERSION file)

[build-system]
requires = ["hatchling"]  # No hatch-vcs needed
```

### Version Reading in Code

```python
from importlib.metadata import version

# Runtime version detection
__version__ = version("omni-dev-fusion-agent")
```

## Why This Strategy?

### Problem with `hatch-vcs` in Sub-packages

When building with `uv build`, the build runs in an isolated environment that may not have access to the parent directory's `.git` folder. This causes `hatch-vcs` to fail with:

```
LookupError: setuptools-scm was unable to detect version for /path/to/subpackage
```

### Solution: Hybrid Approach

1. **Root uses `hatch-vcs`**: For development environment and GitHub Releases
2. **Sub-packages use static versions**: For deterministic builds in CI/CD

This ensures:

- Zero build failures in CI
- Consistent versions across packages
- Automatic version detection during development

## Justfile Commands Reference

| Command                    | Description                      |
| -------------------------- | -------------------------------- |
| `just bump-auto`           | Auto-bump + sync to sub-packages |
| `just bump-patch`          | Patch bump + sync                |
| `just bump-minor`          | Minor bump + sync                |
| `just bump-major`          | Major bump + sync                |
| `just bump-set x.y.z`      | Set explicit version + sync      |
| `just _sync-versions`      | Sync VERSION to all sub-packages |
| `just version`             | Display current version          |
| `just release type="auto"` | Full release workflow            |

## Troubleshooting

### Version not updating after bump

```bash
# Check VERSION file
cat VERSION

# Manual sync
just _sync-versions
```

### Build fails with version error

Ensure sub-packages have static `version` field in `[project]` section.

### Git tag not detected

```bash
# Check existing tags
git tag

# Create a tag
git tag v0.3.0

# Push tags
git push origin v0.3.0
```
