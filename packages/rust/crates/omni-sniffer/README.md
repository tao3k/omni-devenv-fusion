# Omni Sniffer

> High-performance environment sniffer for Omni DevEnv.

## Overview

Omni Sniffer uses libgit2 for fast git operations and provides environment snapshots for code analysis.

## Features

- Fast git repository analysis
- Environment snapshot generation
- File change detection
- Branch and commit information extraction

## Usage

```rust
use omni_sniffer::{OmniSniffer, get_environment_snapshot};

let sniffer = OmniSniffer::new();
let snapshot = sniffer.capture_environment().await?;

println!("Files changed: {}", snapshot.files_changed.len());
```

## Architecture

See [docs/developer/mcp-core-architecture.md](../../../../docs/developer/mcp-core-architecture.md)

## License

Apache-2.0
