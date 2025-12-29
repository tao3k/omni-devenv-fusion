# Justfile for devenv-native
# https://github.com/casey/just

# Load environment variables
set dotenv-load := true
set shell := ["bash", "-uc"]

# Default recipe (show help)
default:
    @just --list

# ==============================================================================
# Setup & Validation
# ==============================================================================

# Setup development environment
setup:
    @echo "Setting up development environment..."
    @direnv allow
    @echo "Ready to develop! Run 'just' to see available commands."

# Validate repository (runs all checks)
validate: check-format check-commits lint test
    @echo "All validation checks passed!"

# Check code formatting
check-format:
    @echo "Checking code formatting..."
    @lefthook run pre-commit --all-files

# Lint all files
lint:
    @echo "Linting files..."
    @lefthook run pre-commit

# Run tests
test:
    @echo "Running tests..."
    @devenv test

# ==============================================================================
# Changelog Management
# ==============================================================================

# Preview changelog for next release
changelog-preview:
    @echo "Changelog Preview (since last tag)"
    @echo "===================================="
    @echo ""
    @cog log --no-pager
    @echo ""
    @echo "===================================="
    @echo "Commit breakdown:"
    @cog log --no-pager | grep -oE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" | sort | uniq -c

# Show changelog statistics
changelog-stats:
    @echo "Changelog Statistics"
    @echo "===================="
    @echo ""
    @echo "Commits by type:"
    @cog log | grep -oE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" | sort | uniq -c | sort -rn
    @echo ""
    @echo "Commits by author:"
    @git log --format='%an' $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD")..HEAD | sort | uniq -c | sort -rn
    @echo ""
    @echo "Changes since last release:"
    @git diff --stat $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD")..HEAD

# Validate all commits follow conventional commits
check-commits:
    @echo "Validating commit messages..."
    @cog check

# Verify specific commit range
check-commits-range from to:
    @echo "Checking commits from {{from}} to {{to}}..."
    @cog check --from {{from}} --to {{to}}

# Generate changelog (manual)
changelog:
    @echo "Generating changelog..."
    @cog changelog

# Generate changelog at specific version
changelog-at version:
    @echo "Generating changelog for {{version}}..."
    @cog changelog --at {{version}}

# Export changelog in multiple formats
changelog-export version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION={{version}}
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    fi
    echo "Exporting changelog for $VERSION..."
    cog changelog --at "$VERSION" > "CHANGELOG_${VERSION}.md"
    echo "  Markdown: CHANGELOG_${VERSION}.md"
    cog log --format json > "CHANGELOG_${VERSION}.json"
    echo "  JSON: CHANGELOG_${VERSION}.json"
    cog changelog --at "$VERSION" | sed 's/\[//' | sed 's/\](.*)$//' > "CHANGELOG_${VERSION}.txt"
    echo "  Plain text: CHANGELOG_${VERSION}.txt"
    echo "Exported changelog in multiple formats"

# ==============================================================================
# Version Management & Releases
# ==============================================================================

# Show current version
version:
    @echo "Current version: $(cat VERSION 2>/dev/null || git describe --tags --abbrev=0 2>/dev/null || echo 'No version found')"

# Bump version automatically (based on conventional commits)
bump-auto: validate
    @echo "Auto-bumping version..."
    @cog bump --auto

# Bump patch version (0.0.X)
bump-patch: validate
    @echo "Bumping patch version..."
    @cog bump --patch

# Bump minor version (0.X.0)
bump-minor: validate
    @echo "Bumping minor version..."
    @cog bump --minor

# Bump major version (X.0.0)
bump-major: validate
    @echo "Bumping major version..."
    @cog bump --major

# Dry run version bump (preview without changes)
bump-dry:
    @echo "Previewing version bump (dry run)..."
    @cog bump --auto --dry-run

# Create pre-release version
bump-pre type="alpha":
    @echo "Creating pre-release ({{type}})..."
    @cog bump --pre {{type}}

# Generate release notes for version
release-notes version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION={{version}}
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(git describe --tags --abbrev=0)
    fi
    echo "# Release $VERSION"
    echo ""
    cog changelog --at "$VERSION" | \
        sed -n "/^## \[v${VERSION#v}\]/,/^## \[v/p" | \
        sed '$d'
    echo ""
    echo "---"
    echo "**Full Changelog**: https://github.com/tao3k/omni-devenv-fusion/compare/$(git describe --tags --abbrev=0 $VERSION^ 2>/dev/null)...$VERSION"

# Publish GitHub release
publish-release version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION={{version}}
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(git describe --tags --abbrev=0)
    fi
    NOTES=$(mktemp)
    just release-notes "$VERSION" > "$NOTES"
    echo "Publishing release $VERSION to GitHub..."
    gh release create "$VERSION" \
        --title "Release $VERSION" \
        --notes-file "$NOTES" \
        --verify-tag
    rm "$NOTES"
    echo "Published release $VERSION"

# Complete release workflow (bump + publish)
release type="auto":
    @echo "Starting release workflow..."
    @just bump-{{type}}
    @just publish-release

# ==============================================================================
# Git Operations
# ==============================================================================

# Show git status with helpful info
status:
    @echo "Repository Status"
    @echo "=================="
    @git status
    @echo ""
    @echo "Current branch: $(git branch --show-current)"
    @echo "Last commit: $(git log -1 --oneline)"
    @echo "Last tag: $(git describe --tags --abbrev=0 2>/dev/null || echo 'No tags')"

# Show recent commits in conventional format
log n="10":
    @cog log --no-pager | head -n {{n}}

# Interactive commit helper (guides conventional commits)
commit:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Interactive Conventional Commit"
    echo "================================"
    echo ""
    echo "Select commit type:"
    select TYPE in feat fix docs style refactor perf test build ci chore; do
        [ -n "$TYPE" ] && break
    done
    read -p "Enter scope (optional, e.g., lefthook, claude): " SCOPE
    SCOPE_STR=""
    if [ -n "$SCOPE" ]; then
        SCOPE_STR="($SCOPE)"
    fi
    read -p "Enter short description: " DESC
    read -p "Add detailed body? [y/N]: " -n 1 ADD_BODY
    echo
    BODY=""
    if [[ $ADD_BODY =~ ^[Yy]$ ]]; then
        echo "Enter body (Ctrl+D when done):"
        BODY=$(cat)
    fi
    read -p "Is this a breaking change? [y/N]: " -n 1 BREAKING
    echo
    FOOTER=""
    if [[ $BREAKING =~ ^[Yy]$ ]]; then
        read -p "Describe the breaking change: " BREAKING_DESC
        FOOTER="BREAKING CHANGE: $BREAKING_DESC"
    fi
    MSG="$TYPE$SCOPE_STR: $DESC"
    if [ -n "$BODY" ]; then
        MSG="$MSG\n\n$BODY"
    fi
    if [ -n "$FOOTER" ]; then
        MSG="$MSG\n\n$FOOTER"
    fi
    echo ""
    echo "Commit message preview:"
    echo "======================="
    echo -e "$MSG"
    echo ""
    read -p "Commit with this message? [Y/n]: " -n 1 CONFIRM
    echo
    if [[ ! $CONFIRM =~ ^[Nn]$ ]]; then
        git commit -m "$(echo -e "$MSG")"
        echo "Committed successfully!"
    else
        echo "Commit cancelled"
        exit 1
    fi

# ==============================================================================
# Development Helpers
# ==============================================================================

# Format all code
fmt:
    @echo "Formatting code..."
    @lefthook run pre-commit --all-files

# Clean generated files
clean:
    @echo "Cleaning generated files..."
    @rm -f CHANGELOG_*.md CHANGELOG_*.json CHANGELOG_*.txt RELEASE_NOTES_*.md
    @echo "Cleaned"

# Update dependencies
update:
    @echo "Updating dependencies..."
    @devenv update
    @echo "Updated"

# Show environment info
info:
    @echo "Environment Information"
    @echo "======================"
    @echo "devenv version: $(devenv version)"
    @echo "nix version: $(nix --version)"
    @echo "just version: $(just --version)"
    @echo "cog version: $(cog --version 2>/dev/null || echo 'not found')"
    @echo "git version: $(git --version)"
    @echo ""
    @echo "Repository: $(git remote get-url origin 2>/dev/null || echo 'no remote')"
    @echo "Branch: $(git branch --show-current)"
    @echo "Version: $(cat VERSION 2>/dev/null || git describe --tags --abbrev=0 2>/dev/null || echo 'unknown')"

# Watch for changes and run checks
watch:
    @echo "Watching for changes..."
    @watchexec -e nix,md,sh -c "just check-format"

# ==============================================================================
# CI/CD Helpers
# ==============================================================================

# Run CI checks (what CI would run)
ci: validate changelog-preview
    @echo "CI checks passed!"

# Prepare for release (pre-release checklist)
pre-release: validate changelog-preview changelog-stats
    @echo ""
    @echo "Pre-release checks complete!"
    @echo ""
    @echo "Next steps:"
    @echo "  1. Review changelog preview above"
    @echo "  2. Run: just bump-auto (or bump-patch/minor/major)"
    @echo "  3. Run: just publish-release"

# ==============================================================================
# Documentation
# ==============================================================================

# Generate documentation index
docs:
    @echo "Documentation Index"
    @echo "==================="
    @echo ""
    @echo "Available documentation:"
    @ls -1 *.md | sed 's/^/  - /'
    @echo ""
    @echo "To view a file: cat <filename>"

# Show commit message examples
examples:
    @echo "Commit Message Examples"
    @echo "======================="
    @echo ""
    @echo "Features:"
    @echo "  feat: add support for custom nixago configurations"
    @echo "  feat(lefthook): add pre-push hook validation"
    @echo ""
    @echo "Bug Fixes:"
    @echo "  fix(omnibus): resolve module import issue"
    @echo "  fix: correct typo in changelog template"
    @echo ""
    @echo "Documentation:"
    @echo "  docs: update CLAUDE.md with justfile workflow"
    @echo "  docs(changelog): add examples for breaking changes"
    @echo ""
    @echo "Refactoring:"
    @echo "  refactor: use map for generator configuration"
    @echo "  refactor(lefthook): simplify hook initialization"
    @echo ""
    @echo "Chores:"
    @echo "  chore(deps): update nixpkgs to latest unstable"
    @echo "  chore: clean up generated files"
    @echo ""
    @echo "Breaking Changes:"
    @echo "  feat(api)!: redesign configuration API"
    @echo ""
    @echo "  BREAKING CHANGE: Configuration API has been redesigned."
    @echo "  Old: config.omnibus = {...}"
    @echo "  New: omnibus.config = {...}"

# ==============================================================================
# Shortcuts (aliases)
# ==============================================================================

# Shortcut for validate
check: validate

# Shortcut for changelog-preview
cl: changelog-preview

# Shortcut for commit
c: commit

# Shortcut for status
s: status

# Shortcut for bump-auto + publish
ship: release
