# Technical Writing Guidelines

## Code-First Documentation

### Command Examples
```bash
# Bad
Run the program using some command

# Good
$ just test-mcp
```

### API References
- Use tables for parameters
- Show input → output examples
- Mention error cases

### File References
- Use relative paths: `mcp-server/git_ops.py`
- Code font for file names: `cog.toml`
- Bold key paths: `**/.claude/**`

### Version-Specific Notes
- Always check the actual tool version with `--version`
- Note version requirements: "Requires nix 2.4+"
