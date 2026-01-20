# Omni Security

> Security scanning utilities for Omni DevEnv.

## Overview

Omni Security provides secret detection and security scanning capabilities for the Omni DevEnv.

## Features

- Secret detection in code
- Security pattern matching
- Compliance checking

## Usage

```rust
use omni_security::{contains_secrets, scan_secrets};

let has_secrets = contains_secrets(&content)?;
let violations = scan_secrets(&content)?;
```

## License

Apache-2.0
