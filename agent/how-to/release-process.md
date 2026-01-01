# Release Process Guide

> **Status**: Active
> **Version**: 1.0.0

## 1. Root Cause Analysis

### Why Did Version Bump Fail Repeatedly?

| Problem | Root Cause | Solution |
|---------|------------|----------|
| Cog skipped v1.3.0 | Remote v1.2.0 tag existed but VERSION was 1.3.0-dev | Delete stale remote tags before bump |
| Merge conflicts in release branch | Previous failed bump left unresolved state | Delete stale release branches |
| Wrong version target | Local tag didn't match remote tag | Sync local/remote tags |
| Release created wrong version | Cog used latest remote tag (v1.2.0) as base | Ensure tags are clean before bump |

### Core Issues

1. **Tag-State Desync**: Local VERSION and remote tags were not synchronized
2. **Stale Artifacts**: Old release branches and tags from failed operations
3. **Cog Behavior**: Uses remote tags to determine version, ignores local VERSION file

## 2. Release Workflow

### Pre-Release Checklist (MANDATORY)

```bash
# 1. Check current state
git status
cat VERSION
git tag | tail -5

# 2. Verify VERSION is in dev state (X.Y.0-dev)
# If VERSION is X.Y.0 (release state), manually set to (X+1).Y.0-dev first

# 3. Clean stale artifacts
git tag -d $(git tag | grep -E "^v$X\." | head -1) 2>/dev/null || true
git push origin :refs/tags/v$X.Y.0 2>/dev/null || true
git branch -D release/$X.Y 2>/dev/null || true

# 4. Ensure main is clean
git switch main && git pull origin main
```

### Standard Release (`just bump-minor`)

```bash
# Pre-conditions:
# - VERSION = X.Y.0-dev
# - Latest tag matches VERSION (or is older)
# - No stale release branches
# - All tests pass

just bump-minor
```

### Manual Release (When Cog Fails)

```bash
# 1. Set release version
echo "X.Y.0" > VERSION
git add VERSION
git commit -m "chore(version): vX.Y.0"

# 2. Create release tag
git tag vX.Y.0

# 3. Create release branch
git branch release/X.Y
git push --set-upstream origin release/X.Y
git push origin vX.Y.0

# 4. Merge back to main
git switch main
git merge release/X.Y --no-ff -m "chore: merge vX.Y.0 release"

# 5. Start next development cycle
echo "X.(Y+1).0-dev" > VERSION
git add VERSION
git commit -m "chore(version): start vX.(Y+1).0 development"
git push origin main
```

## 3. Tag Management Rules

### Tag States

| State | When | Command |
|-------|------|---------|
| Release tag | After version commit | `git tag vX.Y.0` |
| Delete stale | Before new release | `git tag -d vX.Y.0 && git push origin :refs/tags/vX.Y.0` |
| Sync | VERSION mismatch | Delete old, create new |

### Before Every Release

```bash
# Check if tags match expected version
EXPECTED=$(cat VERSION | sed 's/\.0-dev$//')
LATEST_TAG=$(git describe --abbrev=0 --tags 2>/dev/null | sed 's/^v//')

if [ "$EXPECTED" != "$LATEST_TAG" ]; then
    echo "WARNING: VERSION=$EXPECTED but latest tag=v$LATEST_TAG"
    echo "Delete stale tags and re-tag if needed"
fi
```

## 4. Recovery Procedures

### Scenario A: Stale Release Branch with Conflicts

```bash
# Don't try to fix the merge!
git switch main
git branch -D release/X.Y           # Delete stale branch
git push origin --delete release/X.Y # Delete remote
cog bump --minor                     # Cog creates fresh branch
```

### Scenario B: Wrong Tag Version

```bash
# VERSION is 1.4.0 but tag shows v1.2.0
git tag -d v1.2.0                    # Delete wrong local tag
git push origin :refs/tags/v1.2.0    # Delete remote tag
git tag v1.4.0                       # Create correct tag
```

### Scenario C: Bump Created Wrong Version

```bash
# Cog created v1.4.0 but needed v1.3.0
git push origin :refs/tags/v1.4.0    # Delete remote tag
git tag -d v1.4.0                    # Delete local tag
git branch -D release/1.4            # Delete release branch
git push origin --delete release/1.4 # Delete remote branch

# Manually create correct release
echo "1.3.0" > VERSION
git add VERSION
git commit -m "chore(version): v1.3.0"
git tag v1.3.0
# ... continue with manual release steps
```

## 5. Version Numbering Convention

```
MAJOR.MINOR.PATCH
├── MAJOR: Breaking changes, architectural changes
├── MINOR: New features, backward-compatible
└── PATCH: Bug fixes, patches
```

### State Transitions

```
Development (X.Y.0-dev) → Release (X.Y.0) → Development ((X+1).Y.0-dev)
```

## 6. Configuration Source of Truth

| File | Purpose | Update Via |
|------|---------|------------|
| `cog.toml` | Cog configuration | `units/modules/lefthook.nix` (nixago) |
| `VERSION` | Current version | Manual or `cog bump` |
| Tags | Release markers | Manual or `cog bump` |

**IMPORTANT**: Never edit `cog.toml` directly. Modify `units/modules/lefthook.nix` and run `direnv reload`.

## 7. Anti-Patterns to Avoid

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| Manually editing VERSION without syncing tags | Sync local/remote tags first |
| Force pushing to release branches | Create new branch or PR |
| Deleting worktree/repo | Use `git reset --soft` |
| Merging with unresolved conflicts | Delete and recreate branch |
| Editing cog.toml directly | Edit lefthook.nix instead |

## 8. Quick Reference Commands

```bash
# Pre-release check
alias pre-release='echo "VERSION: $(cat VERSION)" && echo "Tags: $(git tag | tail -3)" && echo "Branches: $(git branch | grep release)"'

# Clean stale release artifacts
clean-stale() {
    local ver=$(cat VERSION | cut -d. -f1,2)
    git tag -d v$ver 2>/dev/null || true
    git push origin :refs/tags/v$ver 2>/dev/null || true
    git branch -D release/$ver 2>/dev/null || true
    git push origin --delete release/$ver 2>/dev/null || true
    echo "Cleaned v$ver artifacts"
}

# Manual release helper
release() {
    local ver=$(cat VERSION | sed 's/\.0-dev$//')
    echo "Releasing v$ver..."
    # Steps from Section 2
}
```

## 9. Related Documentation

- [Git Workflow](git-workflow.md) - Commit message standards
- [Feature Lifecycle](../standards/feature-lifecycle.md) - Feature development process
- [CLAUDE.md](../../CLAUDE.md) - Agent instructions

---

*Last updated: 2026-01-01*
