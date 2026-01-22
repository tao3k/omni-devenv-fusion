# omni-core

Microkernel core for omni-dev-fusion.

## Components

- `omni.core.kernel`: Microkernel abstraction layer (Kernel, Lifecycle, Components)
- `omni.core.skills`: Skills system (Registry, Runtime, Discovery, Memory)

## Dependencies

- `omni-foundation`: Foundation layer (Rust bridge, logging, config)
- `mcp`: Model Context Protocol

## Usage

```python
from omni.core.kernel import get_kernel

kernel = get_kernel()
await kernel.initialize()
```
