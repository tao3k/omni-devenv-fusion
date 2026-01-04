# mcp-server/router.py
"""
The Cortex - Semantic Tool Routing System

Responsible for mapping user intent (natural language) to Tool Domains.
This enables the Orchestrator to suggest the right tools for the job,
reducing context overload and improving agent focus.

Domains:
- GitOps: Version control, committing, history.
- ProductOwner: Specs, requirements, compliance.
- Coder: Code exploration, delegation, editing.
- QA: Quality assurance, code review, testing.
- Memory: Context management, tasks, decisions.
- DevOps: Nix, deployment, infrastructure.
"""
import json
from typing import List, Dict, Any
from common.mcp_core import InferenceClient, log_decision

# =============================================================================
# Domain Definitions (The Knowledge Graph)
# =============================================================================

TOOL_DOMAINS = {
    "GitOps": {
        "description": "Version control, commit management, and history.",
        "tools": [
            "smart_commit", "suggest_commit_message", "validate_commit_message",
            "git_status", "git_log", "git_diff", "check_commit_scope"
        ]
    },
    "ProductOwner": {
        "description": "Feature specs, requirements, and archiving.",
        "tools": [
            "draft_feature_spec", "verify_spec_completeness",
            "archive_spec_to_doc",
            "assess_feature_complexity", "verify_design_alignment"
        ]
    },
    "Coder": {
        "description": "Codebase exploration, implementation, and file operations.",
        "tools": [
            "get_codebase_context", "list_directory_structure",
            "delegate_to_coder",
            "ast_search", "ast_rewrite"
        ]
    },
    "QA": {
        "description": "Quality assurance and testing.",
        "tools": [
            "run_tests", "analyze_test_results", "list_test_files",
            "analyze_last_error"
        ]
    },
    "Memory": {
        "description": "Context management, task tracking, and project memory.",
        "tools": [
            "manage_context", "memory_garden"
        ]
    },
    "DevOps": {
        "description": "Infrastructure, Nix configuration, and environment.",
        "tools": [
            "community_proxy", "consult_specialist", "run_task"
        ]
    },
    "Search": {
        "description": "High-performance code search using ripgrep.",
        "tools": [
            "search_project_code"
        ]
    }
}


class ToolRouter:
    def __init__(self, client: InferenceClient = None):
        self.client = client or InferenceClient()

    async def route_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze user query and return the most relevant Tool Domain.
        """
        # Construct the routing prompt
        domains_desc = "\n".join(
            [f"- {name}: {info['description']}" for name, info in TOOL_DOMAINS.items()]
        )

        system_prompt = f"""You are the Cortex of an Agentic OS.
Your job is to route a user's request to the correct Tool Domain.

AVAILABLE DOMAINS:
{domains_desc}

DECISION RULES:
1. **Commit/Version Control** → GitOps (smart_commit, validate_commit_message, git_status, git_log, git_diff)
2. **Testing** → QA (run_tests, analyze_test_results)
3. **Feature Specs** → ProductOwner (draft_feature_spec, verify_spec_completeness)
4. **Code Implementation** → Coder (delegate_to_coder, ast_search, ast_rewrite)
5. **Context/Memory** → Memory (manage_context, memory_garden)
6. **Infrastructure** → DevOps (run_task, consult_specialist)

EXAMPLES:
- "Validate this commit message" → GitOps (uses validate_commit_message)
- "Verify if the latest commit follows our guidelines" → GitOps (commit validation)
- "Run tests and check results" → QA (testing workflow)

Return JSON ONLY: {{ "domain": "Name", "confidence": 0.0-1.0, "reasoning": "..." }}
"""

        user_query = f"User Request: {query}"

        result = await self.client.complete(system_prompt, user_query)

        if not result["success"]:
            return {
                "domain": "Error",
                "confidence": 0.0,
                "reasoning": f"Routing failed: {result['error']}"
            }

        try:
            # Clean up potential markdown code blocks
            content = result["content"].strip()
            if content.startswith("```json"):
                content = content[7:-3]
            elif content.startswith("```"):
                content = content[3:-3]

            routing_data = json.loads(content)

            # Enrich with tool list
            domain = routing_data.get("domain")
            if domain in TOOL_DOMAINS:
                routing_data["suggested_tools"] = TOOL_DOMAINS[domain]["tools"]
            else:
                routing_data["suggested_tools"] = []

            return routing_data

        except json.JSONDecodeError:
            return {
                "domain": "Unknown",
                "confidence": 0.0,
                "reasoning": "Failed to parse router response."
            }


# Singleton instance
_router_instance = None


def get_router():
    global _router_instance
    if _router_instance is None:
        _router_instance = ToolRouter()
    return _router_instance
