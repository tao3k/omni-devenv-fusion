# Justfile for devenv-native
# https://github.com/casey/just
#
# Design principles:
# - Interactive commands for humans (e.g., `just commit`)
# - Agent-friendly commands with `agent-*` prefix (e.g., `just agent-commit "feat" "cli" "message"`)
# - SRE health checks with JSON output for machine parsing
# - Group annotations for clean `just --list` output

# ==============================================================================
# Global Settings
# ==============================================================================

set dotenv-load := true
set shell := ["bash", "-uc"]
set positional-arguments := true

# Enable JSON output mode via environment variable
json_output := if env_var_or_default("JUST_JSON", "false") == "true" { "true" } else { "false" }

# ==============================================================================
# Core Commands
# ==============================================================================

default:
    @just --list

# ==============================================================================
# AGENT INTERFACE (Non-interactive, argument-based)
# Designed for AI agents - accepts parameters, no interactive prompts
# ==============================================================================

# Non-interactive commit for agents
# Usage: just agent-commit <type> <scope> <message> [body] [breaking_desc]
# Example: just agent-commit "feat" "cli" "add new feature" "Detailed description" "BREAKING: API changed"
agent-commit type scope message body="" breaking_desc="":
    #!/usr/bin/env bash
    set -euo pipefail
    TYPE="{{type}}"
    SCOPE="{{scope}}"
    DESC="{{message}}"
    BODY="{{body}}"
    BREAKING_DESC="{{breaking_desc}}"

    # Validate type
    if [[ ! "$TYPE" =~ ^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)$ ]]; then
        echo "Error: Invalid type '$TYPE'. Must be: feat, fix, docs, style, refactor, perf, test, build, ci, chore" >&2
        exit 1
    fi

    # Build scope string
    SCOPE_STR=""
    if [ -n "$SCOPE" ]; then
        SCOPE_STR="($SCOPE)"
    fi

    # Build commit message
    MSG="$TYPE$SCOPE_STR: $DESC"
    if [ -n "$BODY" ]; then
        MSG="$MSG"$'\n\n'"$BODY"
    fi
    if [ -n "$BREAKING_DESC" ]; then
        MSG="$MSG"$'\n\n'"BREAKING CHANGE: $BREAKING_DESC"
    fi

    # Stage all modified files first (handles hook-generated changes like nixfmt)
    echo "Staging all modified files..."
    git add -A

    # Commit with staged changes
    git commit -m "$MSG"
    echo "Committed: $TYPE$SCOPE_STR: $DESC"

# Agent-friendly validate (non-interactive)
agent-validate:
    @echo "Running validation..." && lefthook run pre-commit && devenv test

# Agent-friendly format (apply fixes)
agent-fmt:
    @echo "Applying formatting fixes..." && lefthook run pre-commit --all-files --no-tty

# Agent-friendly version bump
agent-bump type="auto":
    #!/usr/bin/env bash
    set -euo pipefail
    BUMP_TYPE="{{type}}"
    if [ "$BUMP_TYPE" = "auto" ]; then
        cog bump --auto
    else
        cog bump --$BUMP_TYPE
    fi

# Agent-friendly release publish
agent-publish-release version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION="{{version}}"
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(git describe --tags --abbrev=0)
    fi
    NOTES=$(mktemp)
    just release-notes "$VERSION" > "$NOTES"
    gh release create "$VERSION" --title "Release $VERSION" --notes-file "$NOTES" --verify-tag
    rm -f "$NOTES"

# Agent-friendly complete release workflow
agent-release type="auto" version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    just agent-validate
    just agent-bump {{type}}
    just agent-publish-release {{version}}

# ==============================================================================
# HUMAN INTERFACE (Interactive commands preserved)
# Commands with user prompts for manual operations
# ==============================================================================

# Interactive commit helper (for humans - uses select/read)
[group('git')]
commit:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Interactive Conventional Commit"
    echo "================================"
    select TYPE in feat fix docs style refactor perf test build ci chore; do
        [ -n "$TYPE" ] && break
    done
    read -p "Enter scope (optional): " SCOPE
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
    read -p "Breaking change? [y/N]: " -n 1 BREAKING
    echo
    FOOTER=""
    if [[ $BREAKING =~ ^[Yy]$ ]]; then
        read -p "Describe breaking change: " BREAKING_DESC
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
    echo "Preview:"
    echo -e "$MSG"
    echo ""
    read -p "Commit? [Y/n]: " -n 1 CONFIRM
    echo
    if [[ ! $CONFIRM =~ ^[Nn]$ ]]; then
        git commit -m "$(echo -e "$MSG")"
        echo "Committed!"
    else
        echo "Cancelled"
        exit 1
    fi

# ==============================================================================
# SETUP & VALIDATION
# ==============================================================================

[group('setup')]
setup:
    @echo "Setting up development environment..."
    @direnv allow
    @echo "Ready! Run 'just' to see commands."

[group('validate')]
validate: check-format check-commits lint test
    @echo "All validation checks passed!"

[group('validate')]
check-format:
    @echo "Checking code formatting..."
    @lefthook run pre-commit --all-files

[group('validate')]
lint:
    @echo "Linting files..."
    @lefthook run pre-commit

[group('validate')]
test:
    @echo "Running tests..."
    @devenv test

# ==============================================================================
# CHANGELOG MANAGEMENT
# ==============================================================================

[group('changelog')]
changelog-preview:
    @echo "Changelog Preview (since last tag)"
    @echo "===================================="
    @cog log
    @echo ""
    @echo "Commit breakdown:"
    @cog log | grep -oE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" | sort | uniq -c

[group('changelog')]
changelog-stats:
    @echo "Changelog Statistics"
    @echo "===================="
    @echo "Commits by type:"
    @cog log | grep -oE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore)" | sort | uniq -c | sort -rn
    @echo ""
    @echo "Commits by author:"
    @git log --format='%an' $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD")..HEAD | sort | uniq -c | sort -rn
    @echo ""
    @echo "Changes since last release:"
    @git diff --stat $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD")..HEAD

[group('validate')]
check-commits:
    @echo "Validating commit messages..."
    @cog check

[group('validate')]
check-commits-range from to:
    @cog check --from {{from}} --to {{to}}

[group('changelog')]
changelog:
    @echo "Generating changelog..."
    @cog changelog

[group('changelog')]
changelog-at version:
    @cog changelog --at {{version}}

[group('changelog')]
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

# ==============================================================================
# VERSION MANAGEMENT & RELEASES
# ==============================================================================

[group('version')]
version:
    @echo "Current version: $(cat VERSION 2>/dev/null || git describe --tags --abbrev=0 2>/dev/null || echo 'No version found')"

[group('version')]
bump-auto: validate
    @echo "Auto-bumping version..."
    @cog bump --auto

[group('version')]
bump-patch: validate
    @echo "Bumping patch version..."
    @cog bump --patch

[group('version')]
bump-minor: validate
    @echo "Bumping minor version..."
    @cog bump --minor

[group('version')]
bump-major: validate
    @echo "Bumping major version..."
    @cog bump --major

[group('version')]
bump-dry:
    @echo "Previewing version bump (dry run)..."
    @cog bump --auto --dry-run

[group('version')]
bump-pre type="alpha":
    @echo "Creating pre-release ({{type}})..."
    @cog bump --pre {{type}}

[group('version')]
release-notes version="latest":
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION={{version}}
    if [ "$VERSION" = "latest" ]; then
        VERSION=$(git describe --tags --abbrev=0)
    fi
    echo "# Release $VERSION"
    echo ""
    cog changelog --at "$VERSION" | sed -n "/^## \[v${VERSION#v}\]/,/^## \[v/p" | sed '$d'
    echo ""
    echo "---"
    echo "**Full Changelog**: https://github.com/tao3k/omni-devenv-fusion/compare/$(git describe --tags --abbrev=0 $VERSION^ 2>/dev/null)...$VERSION"

[group('version')]
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
    gh release create "$VERSION" --title "Release $VERSION" --notes-file "$NOTES" --verify-tag
    rm -f "$NOTES"
    echo "Published release $VERSION"

[group('version')]
release type="auto":
    @echo "Starting release workflow..."
    @just bump-{{type}}
    @just publish-release

# ==============================================================================
# GIT OPERATIONS
# ==============================================================================

[group('git')]
status:
    @echo "Repository Status"
    @echo "=================="
    @git status
    @echo ""
    @echo "Branch: $(git branch --show-current)"
    @echo "Last commit: $(git log -1 --oneline)"
    @echo "Last tag: $(git describe --tags --abbrev=0 2>/dev/null || echo 'No tags')"

[group('git')]
log n="10":
    @cog log --no-pager | head -n {{n}}

# ==============================================================================
# DEVELOPMENT HELPERS
# ==============================================================================

[group('dev')]
fmt:
    @echo "Formatting code..."
    @lefthook run pre-commit --all-files

[group('dev')]
clean:
    @echo "Cleaning generated files..."
    @rm -f CHANGELOG_*.md CHANGELOG_*.json CHANGELOG_*.txt RELEASE_NOTES_*.md
    @echo "Cleaned"

[group('dev')]
update:
    @echo "Updating dependencies..."
    @devenv update
    @echo "Updated"

[group('dev')]
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

[group('dev')]
watch:
    @echo "Watching for changes..."
    @watchexec -e nix,md,sh -c "just check-format"

# ==============================================================================
# SRE HEALTH CHECKS
# Outputs machine-parseable JSON for AI agents and CI/CD
# ==============================================================================

[group('sre')]
health: health-git health-nix health-secrets health-devenv
    @echo ""
    @echo "Health check complete!"

# Git repository health (JSON optional)
[group('sre')]
health-git:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "${JUST_JSON:-}" = "true" ]; then
        BRANCH=$(git branch --show-current)
        UNCOMMITTED=$(git status --porcelain | wc -l)
        LAST_COMMIT=$(git log -1 --oneline)
        BEHIND=0
        git fetch --quiet 2>/dev/null && BEHIND=$(git log HEAD..origin/$BRANCH 2>/dev/null | wc -l)
        jq -n --arg branch "$BRANCH" --argjson uncommitted "$UNCOMMITTED" --arg last_commit "$LAST_COMMIT" --argjson behind "$BEHIND" \
            '{component: "git", branch: $branch, uncommitted_files: $uncommitted, last_commit: $last_commit, commits_behind: $behind}'
    else
        echo "Git Health"
        echo "=========="
        echo "Branch: $(git branch --show-current)"
        echo "Status: $(git status --porcelain | wc -l) uncommitted files"
        echo "Last commit: $(git log -1 --oneline)"
    fi

# Nix/Devenv health
[group('sre')]
health-nix:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "${JUST_JSON:-}" = "true" ]; then
        NIX_VERSION=$(nix --version 2>/dev/null || echo "")
        jq -n --arg version "$NIX_VERSION" '{component: "nix", version: $version}'
    else
        echo "Nix Health"
        echo "=========="
        echo "Nix version: $(nix --version)"
    fi

# Devenv health
[group('sre')]
health-devenv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "${JUST_JSON:-}" = "true" ]; then
        VERSION=$(devenv version 2>/dev/null || echo "")
        NIXPKGS=$(devenv nixpkgs-version 2>/dev/null || echo "")
        jq -n --arg version "$VERSION" --arg nixpkgs "$NIXPKGS" '{component: "devenv", version: $version, nixpkgs: $nixpkgs}'
    else
        echo "Devenv Health"
        echo "============="
        echo "Version: $(devenv version 2>/dev/null || echo 'not found')"
        echo "Nixpkgs: $(devenv nixpkgs-version 2>/dev/null || echo 'unknown')"
    fi

# Secrets health check (validates presence, never echoes values)
[group('sre')]
health-secrets:
    #!/usr/bin/env bash
    set -euo pipefail
    MISSING=""
    if [ -z "${MINIMAX_API_KEY:-}" ]; then
        MISSING="MINIMAX_API_KEY"
    fi
    if [ "${JUST_JSON:-}" = "true" ]; then
        if [ -z "$MISSING" ]; then
            jq -n '{component: "secrets", status: "pass", message: "All required secrets present"}'
        else
            jq -n --arg missing "$MISSING" \
                '{component: "secrets", status: "fail", message: "Missing secrets", missing_keys: [$missing]}'
            exit 1
        fi
    else
        echo "Secrets Health"
        echo "=============="
        echo "Provider: onepassword"
        if [ -z "$MISSING" ]; then
            echo "Status: OK"
        else
            echo "Status: MISSING - $MISSING"
        fi
    fi

# API keys health (presence check only)
[group('sre')]
health-api-keys:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ "${JUST_JSON:-}" = "true" ]; then
        if [ -n "${MINIMAX_API_KEY:-}" ]; then
            jq -n '{component: "api_keys", minimax: "present"}'
        else
            jq -n '{component: "api_keys", minimax: "missing"}'
            exit 1
        fi
    else
        echo "API Keys Health"
        echo "==============="
        if [ -n "${MINIMAX_API_KEY:-}" ]; then
            echo "MINIMAX_API_KEY: Set"
        else
            echo "MINIMAX_API_KEY: Not set"
        fi
    fi

# Composite health report for agents
[group('sre')]
health-report:
    #!/usr/bin/env bash
    set -euo pipefail
    JUST_JSON=true just health-git
    JUST_JSON=true just health-devenv
    JUST_JSON=true just health-secrets

# ==============================================================================
# CI/CD COMMANDS
# ==============================================================================

[group('ci')]
ci: validate changelog-preview
    @echo "CI checks passed!"

[group('ci')]
pre-release: validate changelog-preview changelog-stats
    @echo ""
    @echo "Pre-release checks complete!"
    @echo ""
    @echo "Next steps:"
    @echo "  1. Review changelog preview"
    @echo "  2. Run: just bump-auto (or bump-patch/minor/major)"
    @echo "  3. Run: just publish-release"

# ==============================================================================
# SECRET MANAGEMENT (secretspec)
# ==============================================================================

[group('secrets')]
secrets-check:
    @echo "Checking secrets status..."
    @secretspec check --profile development

[group('secrets')]
secrets-info:
    @echo "Secret Management Info"
    @echo "======================"
    @echo "Provider: onepassword"
    @echo "Profile: development"
    @echo ""
    @echo "Configured secrets:"
    @secretspec check --profile development | grep -E "^\s+[A-Z]" || echo "  (none)"

[group('secrets')]
secrets-set-minimax:
    #!/usr/bin/env bash
    set -euo pipefail
    read -p "Enter MINIMAX_API_KEY: " -s API_KEY
    echo
    secretspec set MINIMAX_API_KEY --value "$API_KEY" --profile development
    echo "MINIMAX_API_KEY set"

[group('secrets')]
secrets-get-minimax:
    @secretspec get MINIMAX_API_KEY

# ==============================================================================
# DOCUMENTATION
# ==============================================================================

[group('docs')]
docs:
    @echo "Documentation Index"
    @echo "==================="
    @echo ""
    @echo "Available documentation:"
    @ls -1 *.md | sed 's/^/  - /'

[group('docs')]
examples:
    @echo "Commit Message Examples"
    @echo "======================="
    @echo ""
    @echo "feat: add new feature"
    @echo "feat(cli): add command"
    @echo "fix: correct bug"
    @echo "docs: update documentation"
    @echo "refactor: reorganize code"
    @echo "chore: maintenance tasks"
    @echo ""
    @echo "feat(api)!: breaking change"
    @echo "BREAKING CHANGE: description"

# ==============================================================================
# ALIASES (using recipe definitions instead of variable assignments)
# ==============================================================================

check: validate
cl: changelog-preview
c: commit
s: status
ship: release

# Compatibility aliases for agent-* pattern
agent-ci: agent-validate
agent-test: test
agent-lint: lint
agent-format: fmt
