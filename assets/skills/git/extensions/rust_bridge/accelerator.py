"""accelerator.py - Rust Acceleration Layer.

Git Rust accelerator that provides high-performance operations.
Falls back gracefully if Rust bindings are unavailable.
"""

from typing import Any, Dict, List, Optional
from .bindings import RustBindings, is_rust_available


class RustAccelerator:
    """Git Rust Accelerator - provides high-performance Git operations."""

    def __init__(self, repo_path: str):
        """Initialize the accelerator with a repository path.

        Args:
            repo_path: Path to the Git repository
        """
        # Initialize _sniffer first to avoid AttributeError in setter
        self._sniffer = None
        self._repo_path = repo_path
        self._init_sniffer()

    def _init_sniffer(self) -> None:
        """Initialize the Rust sniffer if available."""
        if is_rust_available():
            sniffer_cls = RustBindings.get_sniffer_cls()
            if sniffer_cls:
                try:
                    self._sniffer = sniffer_cls(self.repo_path)
                except Exception as e:
                    # Repo might not exist or be a git repo
                    pass

    @property
    def is_active(self) -> bool:
        """Check if the Rust accelerator is active."""
        return self._sniffer is not None

    @property
    def repo_path(self) -> str:
        """Get the repository path."""
        return self._repo_path

    @repo_path.setter
    def repo_path(self, value: str) -> None:
        """Set repository path and reinitialize."""
        self._repo_path = value
        if self._sniffer is not None:
            self._init_sniffer()

    def status(self) -> Dict[str, Any]:
        """Get Git repository status using Rust.

        Returns:
            Dictionary with status information
        """
        if self._sniffer:
            try:
                return self._sniffer.status()
            except Exception:
                pass
        return {}

    def log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get Git commit log using Rust.

        Args:
            limit: Maximum number of commits to return

        Returns:
            List of commit dictionaries
        """
        if self._sniffer:
            try:
                return self._sniffer.log(limit)
            except Exception:
                pass
        return []

    def branch_info(self) -> Dict[str, Any]:
        """Get current branch information using Rust.

        Returns:
            Dictionary with branch information
        """
        if self._sniffer:
            try:
                return self._sniffer.branch_info()
            except Exception:
                pass
        return {}

    def staged_files(self) -> List[str]:
        """Get list of staged files using Rust.

        Returns:
            List of staged file paths
        """
        if self._sniffer:
            try:
                return self._sniffer.staged_files()
            except Exception:
                pass
        return []

    def modified_files(self) -> List[str]:
        """Get list of modified (but not staged) files using Rust.

        Returns:
            List of modified file paths
        """
        if self._sniffer:
            try:
                return self._sniffer.modified_files()
            except Exception:
                pass
        return []


def create_accelerator(repo_path: str) -> RustAccelerator:
    """Factory function to create a Rust accelerator.

    Args:
        repo_path: Path to the Git repository

    Returns:
        RustAccelerator instance
    """
    return RustAccelerator(repo_path)
