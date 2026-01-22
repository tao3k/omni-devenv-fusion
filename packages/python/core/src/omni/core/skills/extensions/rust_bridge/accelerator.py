"""accelerator.py - Core Rust Accelerator.

Generic Rust accelerator that wraps Rust bindings.
Skills can inject this into their script context for high-performance operations.

New API:
- RustVectorStore: High-performance vector operations
- RustCodeAnalyzer: Code analysis with ast-grep
- RustSkillScanner: Skill structure scanning

Usage:
    from omni.core.skills.extensions import SkillExtensionLoader

    loader = SkillExtensionLoader("/path/to/skill/extensions")
    loader.load_all()

    bridge = loader.get("rust_bridge")
    accelerator = bridge.create_accelerator("/path/to/repo")
"""

from typing import Any

import structlog

logger = structlog.get_logger("omni.core.ext.rust.accelerator")


class RustAccelerator:
    """Generic Rust accelerator for high-performance operations.

    This class wraps Rust bindings and provides a unified interface
    for skills to access Rust-accelerated functionality.

    Usage:
        # Loaded automatically by UniversalScriptSkill
        # Scripts receive 'rust' variable automatically

        def my_command():
            if rust and rust.is_active:
                return rust.execute_fast_operation()
            else:
                return python_fallback_operation()
    """

    def __init__(self, repo_path: str = "."):
        """Initialize the Rust accelerator.

        Args:
            repo_path: Path to the repository/project root
        """
        self._repo_path = repo_path
        self._bindings: dict[str, Any] = {}
        self._is_active = False
        self._initialize()

    def _initialize(self):
        """Initialize Rust bindings."""
        # Try to load available Rust bindings
        available = []

        # Vector Store
        try:
            from omni.foundation.bridge import RustVectorStore

            self._bindings["vector"] = RustVectorStore()
            available.append("RustVectorStore")
        except ImportError as e:
            logger.debug(f"RustVectorStore not available: {e}")

        # Code Analyzer
        try:
            from omni.foundation.bridge import RustCodeAnalyzer

            self._bindings["analyzer"] = RustCodeAnalyzer()
            available.append("RustCodeAnalyzer")
        except ImportError as e:
            logger.debug(f"RustCodeAnalyzer not available: {e}")

        # Skill Scanner
        try:
            from omni.foundation.bridge import RustSkillScanner

            self._bindings["scanner"] = RustSkillScanner()
            available.append("RustSkillScanner")
        except ImportError as e:
            logger.debug(f"RustSkillScanner not available: {e}")

        self._is_active = len(available) > 0

        if self._is_active:
            logger.info(
                f"Rust accelerator active for {self._repo_path}",
                bindings=available,
            )
        else:
            logger.warning("No Rust bindings available - using Python fallbacks")

    @property
    def is_active(self) -> bool:
        """Check if Rust accelerator is available and active."""
        return self._is_active

    @property
    def repo_path(self) -> str:
        """Get the repository path."""
        return self._repo_path

    @property
    def vector_store(self):
        """Get the vector store binding."""
        return self._bindings.get("vector")

    @property
    def code_analyzer(self):
        """Get the code analyzer binding."""
        return self._bindings.get("analyzer")

    @property
    def skill_scanner(self):
        """Get the skill scanner binding."""
        return self._bindings.get("scanner")

    def status(self) -> dict[str, Any]:
        """Get the current status from Rust bindings.

        Returns:
            Dictionary with status information
        """
        return {
            "available": self._is_active,
            "repo_path": self._repo_path,
            "bindings": list(self._bindings.keys()),
        }

    def execute(self, operation: str, **kwargs) -> Any:
        """Execute a Rust-accelerated operation.

        Args:
            operation: Name of the operation to execute (vector, analyzer, scanner)
            **kwargs: Operation-specific arguments

        Returns:
            Result from Rust operation
        """
        if not self._is_active:
            raise RuntimeError("Rust accelerator is not active")

        # Parse operation: "vector.search", "analyzer.analyze", etc.
        parts = operation.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid operation format: {operation}")

        binding_name, method = parts
        binding = self._bindings.get(binding_name)

        if binding is None:
            raise ValueError(f"Unknown binding: {binding_name}")

        method_fn = getattr(binding, method, None)
        if method_fn is None:
            raise AttributeError(f"{binding_name} has no method: {method}")

        return method_fn(**kwargs)

    def __repr__(self) -> str:
        status = "active" if self._is_active else "inactive"
        bindings = list(self._bindings.keys())
        return f"<RustAccelerator path='{self._repo_path}' status='{status}' bindings={bindings}>"


def create_accelerator(repo_path: str = ".") -> RustAccelerator:
    """Factory function to create a RustAccelerator.

    Args:
        repo_path: Path to the repository/project root

    Returns:
        RustAccelerator instance
    """
    return RustAccelerator(repo_path)
