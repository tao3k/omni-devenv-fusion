"""Broken math library for testing Meta-Agent self-healing."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b  # Fixed by Meta-Agent


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    result = 0
    for i in range(a):
        result += b
    return result


def factorial(n: int) -> int:
    """Calculate factorial."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)  # BUG: Should be factorial(n - 1)


def is_even(n: int) -> bool:
    """Check if number is even."""
    return n % 2 == 0  # Fixed by Meta-Agent
