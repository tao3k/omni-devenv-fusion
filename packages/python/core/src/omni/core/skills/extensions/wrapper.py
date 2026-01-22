"""wrapper.py - Extension Object Proxy.

A lightweight proxy class that wraps dynamically loaded Python modules/objects.
Provides attribute-style access to plugin content: extension.some_function()
"""

from __future__ import annotations

from typing import Any


class ExtensionWrapper:
    """Extension Object Proxy.

    Wraps dynamically loaded Python modules or objects.
    Allows attribute-style access: extension.some_function()

    Example:
        wrapper = ExtensionWrapper(module, "rust_bridge")
        result = wrapper.initialize(context)  # Calls module.initialize()
    """

    __slots__ = ("_module", "_name")

    def __init__(self, module: Any, name: str) -> None:
        """Initialize wrapper.

        Args:
            module: The loaded Python module object
            name: Extension name for identification
        """
        self._module = module
        self._name = name

    def __getattr__(self, name: str) -> Any:
        """Forward all attribute access to the wrapped module."""
        return getattr(self._module, name)

    def __repr__(self) -> str:
        return f"<ExtensionWrapper name='{self._name}'>"

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to module attributes."""
        return getattr(self._module, key)

    def __contains__(self, key: str) -> bool:
        """Check if attribute exists on wrapped module."""
        return hasattr(self._module, key)

    def __iter__(self):
        """Iterate over module attributes."""
        return iter(dir(self._module))

    @property
    def name(self) -> str:
        """Extension name."""
        return self._name

    @property
    def module(self) -> Any:
        """Get the raw module object for advanced reflection."""
        return self._module

    def call(self, func_name: str, *args, **kwargs) -> Any:
        """Call a function on the wrapped module.

        Args:
            func_name: Name of the function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the function call
        """
        func = getattr(self._module, func_name)
        return func(*args, **kwargs)
