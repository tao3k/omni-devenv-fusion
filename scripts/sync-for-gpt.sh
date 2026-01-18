#!/usr/bin/env bash
#
# Sync project source files for GPT analysis
# Excludes: compiled files, caches, binaries, etc.
#

set -euo pipefail

SRC_DIR="$PRJ_ROOT"
DEST_DIR="$HOME/ghq/github.com/tao3k/omni-devenv-fusion-gpt"

echo "Syncing from: $SRC_DIR"
echo "Syncing to:   $DEST_DIR"

# Create destination directory
mkdir -p "$DEST_DIR"

# rsync with exclusions:
# - .git: git metadata
# - __pycache__: Python bytecode cache
# - *.pyc: Python compiled files
# - *.so: Shared object files
# - .venv, .direnv: Virtual environments
# - target: Rust build output
# - .data, .cache, .bin: Cache directories
# - node_modules: Node packages
# - .pytest_cache: pytest cache
# - *.egg-info: Python package info
# - .ruff_cache, .mypy_cache: Linter caches
# - .claude/: Claude settings
# - .env*: Environment files

rsync -av --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.so' \
  --exclude='.venv' \
  --exclude='.direnv' \
  --exclude='target' \
  --exclude='.data' \
  --exclude='.cache' \
  --exclude='.bin' \
  --exclude='node_modules' \
  --exclude='.pytest_cache' \
  --exclude='*.egg-info' \
  --exclude='.ruff_cache' \
  --exclude='.mypy_cache' \
  --exclude='.claude' \
  --exclude='.env' \
  --exclude='.env.development' \
  --exclude='.devenv*' \
  --exclude='devenv.local.nix' \
  --exclude='.mcp.json' \
  --exclude='.run' \
  --exclude='cog.toml' \
  --exclude='.conform.yaml' \
  --exclude='lefthook.yml' \
  --exclude='.config' \
  --exclude='.html' \
  --exclude='*.bak' \
  --exclude='.pre-commit-config.yaml' \
  --exclude='process-compose.log' \
  --exclude='.python-version' \
  \
  "$SRC_DIR/docs" \
  "$SRC_DIR/packages" \
  "$SRC_DIR/assets" \
  "$SRC_DIR/.gitignore" \
  "$SRC_DIR/CLAUDE.md" \
  "$SRC_DIR/README.md" \
  "$DEST_DIR/"

echo ""
echo "Sync complete!"
echo "Destination size:"
du -sh "$DEST_DIR" 2>/dev/null || echo "N/A"
