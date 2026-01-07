"""
execution - Safe command execution module.

Phase 29: Protocol-based design with slots=True.

Modules:
- protocols.py: ISafeExecutor, ISecurityChecker protocols
- security.py: Dangerous pattern detection and whitelist checking
- executor.py: SafeExecutor class

Usage:
    from mcp_core.execution import SafeExecutor, check_dangerous_patterns

    result = await SafeExecutor.run("just", ["test"])
    result = await SafeExecutor.run_sandbox("echo", ["hello"])
"""

from .protocols import ISafeExecutor, ISecurityChecker
from .security import (
    DANGEROUS_PATTERNS,
    DEFAULT_ALLOWED_COMMANDS,
    check_dangerous_patterns,
    check_whitelist,
    create_sandbox_env,
)
from .executor import SafeExecutor

__all__ = [
    # Protocols
    "ISafeExecutor",
    "ISecurityChecker",
    # Security
    "DANGEROUS_PATTERNS",
    "DEFAULT_ALLOWED_COMMANDS",
    "check_dangerous_patterns",
    "check_whitelist",
    "create_sandbox_env",
    # Executor
    "SafeExecutor",
]
