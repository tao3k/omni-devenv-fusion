# Omni IO

> File I/O utilities for Omni DevEnv.

## Features

- Safe file reading with token counting
- Truncation for large files
- Path normalization

## Usage

```rust
use omni_io::{read_file_safe, truncate_tokens};

let content = read_file_safe("large_file.md", 1000)?;
```

## License

Apache-2.0
