"""
Verification script for Python 3.12+ Toolchain.
Running `ruff check` on this file should trigger multiple UP (pyupgrade) warnings.
"""
import asyncio
from enum import Enum
from typing import TypeVar

# 1. Old Generics (Should suggest: class Box[T]:)
T = TypeVar("T")

class Box:  # Should suggest removing (object)
    def __init__(self, value: T):
        self.value = value

# 2. Old Union Syntax (Should suggest: int | str)
def process(x: int | str) -> list[str] | None:
    # 3. Old built-in calls (Should suggest: list() -> [])
    return list()

# 4. Old Enum (Should suggest: StrEnum if imported)
class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

async def old_concurrency():
    # 5. Should warn about asyncio.gather if strict rules enabled (optional)
    await asyncio.gather(asyncio.sleep(1), asyncio.sleep(2))
