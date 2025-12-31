# mcp-server/git_ops.py
"""
Git Operations - Config-Driven Smart Commit Workflow

Tools for safe, protocol-compliant Git operations:
- smart_commit: Execute commits following Agent-Commit Protocol
- validate_commit_message: Check against cog.toml/.conform.yaml rules
- check_commit_scope: Verify scope against active configuration
- suggest_commit_message: AI-powered commit generation based on real config
- spec_aware_commit: Generate commit from Spec + Scratchpad (Phase 5)

Configuration Source of Truth:
1. cog.toml (Primary for scopes)
2. .conform.yaml (Primary for types, if available)
3. docs/how-to/git-workflow.md (Fallback)
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Try to import tomllib (Python 3.11+) for parsing cog.toml
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Fallback for older python if installed

# =============================================================================
# Singleton Cache - Rules loaded dynamically from Config Files
# =============================================================================

class GitRulesCache:
    """
    Singleton cache that reads cog.toml and .conform.yaml to determine
    valid commit scopes and types.
    """
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not GitRulesCache._loaded:
            self.valid_types = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore"]
            self.project_scopes = []
            self._load_configuration()
            GitRulesCache._loaded = True

    def _load_configuration(self):
        """Load rules from configuration files (Priority: Config > Doc > Default)"""

        # Determine project root (handles mcp-server/ subdirectory)
        module_dir = Path(__file__).parent.resolve()
        project_root = module_dir.parent.resolve()  # Go up from mcp-server/

        # 1. Load Scopes from cog.toml (Highest Priority for Scopes)
        cog_path = project_root / "cog.toml"
        if cog_path.exists():
            try:
                with open(cog_path, "rb") as f:
                    data = tomllib.load(f)
                    # cog.toml: scopes = ["nix", "mcp", ...]
                    if "scopes" in data:
                        self.project_scopes = data["scopes"]
            except Exception as e:
                print(f"[GitOps] Failed to parse cog.toml: {e}", file=sys.stderr)

        # 2. Load Types from .conform.yaml (Highest Priority for Types)
        conform_path = project_root / ".conform.yaml"
        if conform_path.exists():
            try:
                # Simple parser to avoid heavy PyYAML dependency if not present
                # Looking for keys like: - type: feat
                content = conform_path.read_text(encoding="utf-8")
                import re
                found_types = re.findall(r'-\s+type:\s+([a-zA-Z0-9]+)', content)
                if found_types:
                    self.valid_types = list(set(found_types)) # deduplicate
            except Exception as e:
                print(f"[GitOps] Failed to parse .conform.yaml: {e}", file=sys.stderr)

        # 3. Fallback to Markdown parsing only if config missing
        if not self.project_scopes:
            self._load_from_markdown()

    def _load_from_markdown(self):
        """Fallback: Parse docs/how-to/git-workflow.md"""
        module_dir = Path(__file__).parent.resolve()
        project_root = module_dir.parent.resolve()
        doc_path = project_root / "docs/how-to/git-workflow.md"
        if not doc_path.exists():
            return

        try:
            content = doc_path.read_text(encoding="utf-8")
            import re
            # Extract scopes table
            scope_section = re.search(r"### Suggested Scopes.*?(?=##)", content, re.DOTALL)
            if scope_section:
                scope_rows = re.findall(r"\|\s*`([^`]+)`\s*\|\s*[^|]+\s*\|", scope_section.group())
                valid_scopes = ["nix", "mcp", "router", "docs", "cli", "deps", "ci", "data"]
                self.project_scopes = [s for s in scope_rows if s in valid_scopes]
        except Exception:
            pass

    def get_types(self) -> List[str]:
        return self.valid_types

    def get_scopes(self) -> List[str]:
        return self.project_scopes

    def reload(self):
        self._load_configuration()


_git_rules_cache = GitRulesCache()

# =============================================================================
# Helper Functions
# =============================================================================

def _validate_type(msg_type: str) -> tuple[bool, str]:
    valid_types = _git_rules_cache.get_types()
    if msg_type.lower() not in valid_types:
        return False, f"Invalid type '{msg_type}'. Allowed: {', '.join(valid_types)}"
    return True, ""

def _validate_scope(scope: str, allow_empty: bool = True) -> tuple[bool, str]:
    if not scope:
        return (True, "") if allow_empty else (False, "Scope is required")

    valid_scopes = _git_rules_cache.get_scopes()
    # If no scopes are defined in config, we might allow any, but here we strict check if config exists
    if valid_scopes and scope.lower() not in valid_scopes:
        return False, f"Invalid scope '{scope}'. Allowed: {', '.join(valid_scopes)}"
    return True, ""

def _validate_message_format(message: str) -> tuple[bool, str]:
    if not message or len(message.strip()) < 3:
        return False, "Message too short"
    if message.endswith('.'):
        return False, "Message should not end with period"
    if message[0].isupper():
        return False, "Message should start with lowercase"
    return True, ""

def _validate_message(message: str) -> tuple[bool, str]:
    """Alias for backward compatibility."""
    return _validate_message_format(message)

# =============================================================================
# MCP Tools
# =============================================================================

def register_git_ops_tools(mcp: Any) -> None:
    """Register all git operations tools."""

    @mcp.tool()
    async def validate_commit_message(type: str, scope: str, message: str) -> str:
        """
        Validate a commit message against active config (cog.toml/.conform.yaml).
        """
        violations = []

        v, e = _validate_type(type)
        if not v: violations.append(e)

        v, e = _validate_scope(scope)
        if not v: violations.append(e)

        v, e = _validate_message_format(message)
        if not v: violations.append(e)

        if violations:
            return json.dumps({"valid": False, "violations": violations}, indent=2)

        return json.dumps({"valid": True, "formatted": f"{type}({scope}): {message}"}, indent=2)

    @mcp.tool()
    async def smart_commit(type: str, scope: str, message: str, force_execute: bool = False) -> str:
        """
        Execute a commit. Enforces `just agent-commit` workflow.
        """
        # 1. Re-validate against dynamic rules
        v_type, e_type = _validate_type(type)
        v_scope, e_scope = _validate_scope(scope)
        v_msg, e_msg = _validate_message_format(message)

        if not v_type or not v_scope or not v_msg:
            return json.dumps({
                "status": "error",
                "violations": [e for e in [e_type, e_scope, e_msg] if e]
            }, indent=2)

        if not force_execute:
            return json.dumps({
                "status": "ready",
                "protocol": "stop_and_ask",
                "message": "Changes validated against cog.toml. Ready to commit.",
                "command": f"just agent-commit {type.lower()} {scope.lower() if scope else ''} \"{message}\"",
                "authorization_required": True,
                "user_prompt_hint": "Reply 'run just agent-commit' to authorize"
            }, indent=2)

        # Execute
        cmd = ["just", "agent-commit", type.lower(), scope.lower() if scope else '', message]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode == 0:
            return json.dumps({"status": "success", "output": res.stdout}, indent=2)
        else:
            return json.dumps({"status": "error", "error": res.stderr, "stdout": res.stdout}, indent=2)

    @mcp.tool()
    async def suggest_commit_message(spec_path: str = None) -> str:
        """
        [Publisher Tool] Generates a Conventional Commit message based on staged changes and CONFIG.

        It reads `cog.toml` to understand valid scopes, ensuring the AI suggestion
        is always valid against the project's linter.
        """
        # 1. Get Staged Changes
        diff_proc = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True)
        diff = diff_proc.stdout.strip()
        if not diff:
            return "Error: No staged changes. Did you run `git add`?"

        # 2. Prepare Dynamic Context from Config
        valid_types = _git_rules_cache.get_types()
        valid_scopes = _git_rules_cache.get_scopes()

        scopes_prompt = f"Allowed Scopes (from cog.toml): {', '.join(valid_scopes)}" if valid_scopes else "Scopes: Infer from context (no strict config found)"
        types_prompt = f"Allowed Types: {', '.join(valid_types)}"

        # 3. Get Context (Spec + Memory)
        context_str = ""
        if spec_path:
            sp = Path(spec_path)
            if sp.exists():
                context_str += f"\n--- SPEC ({spec_path}) ---\n{sp.read_text(encoding='utf-8')[:1000]}...\n"

        try:
            from mcp_core.memory import ProjectMemory
            memory = ProjectMemory()
            status = memory.get_status()
            context_str += f"\n--- MEMORY STATUS ---\n{status}\n"
        except ImportError:
            pass

        # 4. Call LLM
        try:
            from mcp_core import InferenceClient
            client = InferenceClient()
        except ImportError:
            return "Error: mcp_core not found."

        system_prompt = f"""You are a Senior Release Engineer.
Generate a Conventional Commit message for these changes.

CONFIGURATION (STRICT):
1. {types_prompt}
2. {scopes_prompt}
3. Subject: Imperative mood, lowercase, no period.

INPUTS:
- Diff: Staged code changes.
- Spec: The feature requirement (optional).
- Memory: Recent developer context (optional).

Reflect on the Diff. Match it to the most specific Scope from the allowed list.
"""

        user_prompt = f"""Generate commit details for:

--- STAGED CHANGES ---
{diff[:3000]}
--- END CHANGES ---

{context_str}

Return ONLY a JSON object: {{ "type": "...", "scope": "...", "message": "...", "body": "..." }}"""

        result = await client.complete(system_prompt=system_prompt, user_query=user_prompt)

        if not result.get("success", False):
            return f"Error generating message: {result.get('error', 'Unknown error')}"

        content = result.get("content", "{}")
        return f"""✅ Suggested Commit (Config-Aligned):
```json
{content}

```

Next: Run `smart_commit` with these values."""

    @mcp.tool()
    async def spec_aware_commit(spec_path: str = None, force_execute: bool = False) -> str:
        """
        [Phase 5 - Smart Commit] Generate commit message from Spec + Scratchpad.

        This tool implements "Spec-Aware GitOps":
        1. Reads the Spec file to extract Context & Goal
        2. Reads Scratchpad for recent activity
        3. Uses AI to generate high-quality commit message (Why, What, How)
        """
        # 1. Gather context from Spec
        spec_content = ""
        spec_title = "Unknown"
        if spec_path:
            sp = Path(spec_path)
            if sp.exists():
                spec_content = sp.read_text(encoding="utf-8")
                spec_title = spec_content.split('\n')[0].replace('# ', '').strip()

        # 2. Gather context from Scratchpad
        scratchpad_content = ""
        try:
            from mcp_core.memory import ProjectMemory
            memory = ProjectMemory()
            scratchpad_path = memory.active_dir / "SCRATCHPAD.md"
            if scratchpad_path.exists():
                scratchpad_content = scratchpad_path.read_text(encoding="utf-8")
                lines = scratchpad_content.split('\n')
                scratchpad_content = '\n'.join(lines[-30:])
        except ImportError:
            pass

        # 3. Generate commit message using AI
        if spec_content:
            try:
                from mcp_core import InferenceClient
                inference = InferenceClient()
            except ImportError:
                return "Error: mcp_core InferenceClient not found."

            valid_types = _git_rules_cache.get_types()
            valid_scopes = _git_rules_cache.get_scopes()

            system_prompt = f"""You are a Principal Software Architect generating a Conventional Commit message.

RULES:
- Type: {', '.join(valid_types)}
- Scope: {', '.join(valid_scopes) if valid_scopes else 'Infer from context'}
- Message: Imperative, lowercase start, no period
- Body: Explain WHY and HOW

Output format (JSON only):
{{ "type": "...", "scope": "...", "message": "...", "body": "..." }}"""

            user_query = f"""## Spec: {spec_title}
{spec_content[:2000]}

## Recent Activity
{scratchpad_content[-1000:]}

Return JSON only."""

            result = inference.complete(system_prompt=system_prompt, user_query=user_query)

            import re
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                commit_data = json.loads(json_match.group())
                generated_type = commit_data.get("type", "chore")
                generated_scope = commit_data.get("scope", "")
                generated_message = commit_data.get("message", "update files")
                generated_body = commit_data.get("body", "")
            else:
                generated_type, generated_scope, generated_message, generated_body = "chore", "", "update files", ""
        else:
            generated_type, generated_scope, generated_message, generated_body = "chore", "", "update files", ""

        # 4. Validate
        v_type, _ = _validate_type(generated_type)
        if not v_type: generated_type = "chore"

        v_scope, _ = _validate_scope(generated_scope)
        if not v_scope: generated_scope = ""

        # 5. Build command
        scope_str = f"({generated_scope})" if generated_scope else ""
        commit_msg = f"{generated_type}{scope_str}: {generated_message}"

        if not force_execute:
            return json.dumps({
                "status": "ready",
                "protocol": "spec_aware_commit",
                "spec": spec_title,
                "message": commit_msg,
                "body": generated_body,
                "command": f"just agent-commit {generated_type} {generated_scope or ''} \"{generated_message}\"",
                "authorization_required": True,
                "note": "AI-generated commit message from Spec + Scratchpad"
            }, indent=2)

        # Execute
        try:
            body_arg = generated_body.replace('"', '\\"') if generated_body else ""
            result = subprocess.run(
                ["just", "agent-commit", generated_type, generated_scope or '', generated_message, body_arg],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                return json.dumps({
                    "status": "success",
                    "message": "Commit executed successfully",
                    "spec": spec_title,
                    "commit": commit_msg,
                    "output": result.stdout
                }, indent=2)
            else:
                return json.dumps({
                    "status": "error",
                    "message": "Commit failed",
                    "error": result.stderr
                }, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)}, indent=2)

    @mcp.tool()
    async def check_commit_scope(scope: str) -> str:
        """Check if a scope is valid in cog.toml."""
        v, e = _validate_scope(scope)
        if v:
            return json.dumps({"valid": True, "scope": scope, "message": "Valid scope"}, indent=2)
        return json.dumps({"valid": False, "scope": scope, "message": e, "allowed_scopes": _git_rules_cache.get_scopes()}, indent=2)

    @mcp.tool()
    async def load_git_workflow_memory() -> str:
        """
        Load full git-workflow.md as persistent memory.
        """
        doc_path = Path("docs/how-to/git-workflow.md")
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            return json.dumps({
                "status": "success",
                "source": "docs/how-to/git-workflow.md",
                "memory": content
            }, indent=2)
        return json.dumps({"status": "error", "message": "git-workflow.md not found"}, indent=2)

    @mcp.tool()
    async def git_status() -> str:
        """Show working tree status."""
        _git_rules_cache.get_types()  # Ensure cache loaded
        result = subprocess.run(["git", "status"], capture_output=True, text=True)
        return json.dumps({
            "status": "success" if result.returncode == 0 else "error",
            "rules_loaded": True,
            "source": "cog.toml/.conform.yaml",
            "output": result.stdout,
            "stderr": result.stderr if result.stderr else None
        }, indent=2)

    @mcp.tool()
    async def git_log(n: int = 10) -> str:
        """Show recent commit history."""
        _git_rules_cache.get_types()
        result = subprocess.run(["git", "log", f"-{n}", "--oneline"], capture_output=True, text=True)
        return json.dumps({
            "status": "success",
            "rules_loaded": True,
            "commits": [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        }, indent=2)

    @mcp.tool()
    async def git_diff() -> str:
        """Show unstaged changes."""
        _git_rules_cache.get_types()
        result = subprocess.run(["git", "diff"], capture_output=True, text=True)
        return json.dumps({
            "status": "success",
            "has_changes": bool(result.stdout.strip()),
            "diff": result.stdout if result.stdout else None
        }, indent=2)

    @mcp.tool()
    async def git_diff_staged() -> str:
        """Show staged changes."""
        _git_rules_cache.get_types()
        result = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True)
        return json.dumps({
            "status": "success",
            "has_staged_changes": bool(result.stdout.strip()),
            "staged_diff": result.stdout if result.stdout else None
        }, indent=2)


def _get_scope_description(scope: str) -> str:
    """Get description for a scope."""
    descriptions = {
        "nix": "Infrastructure: devenv.nix, modules",
        "mcp": "Application: mcp-server logic",
        "router": "Logic: Tool routing & intent",
        "docs": "Documentation",
        "cli": "Tooling: justfile, lefthook",
        "deps": "Dependency management",
        "ci": "GitHub Actions, DevContainer",
        "data": "JSONL examples, assets",
    }
    return descriptions.get(scope, "Unknown scope")


# =============================================================================
# Export
# =============================================================================

__all__ = ["register_git_ops_tools", "GitRulesCache"]
