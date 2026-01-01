"""Tests for mcp-server/router.py (The Cortex - Semantic Tool Routing)."""
import pytest
import asyncio

from router import get_router, TOOL_DOMAINS


class TestRouterBasics:
    """Basic router functionality tests."""

    def test_domains_defined(self):
        """All expected domains should be defined."""
        expected_domains = ["GitOps", "ProductOwner", "Coder", "QA", "Memory", "DevOps"]
        for domain in expected_domains:
            assert domain in TOOL_DOMAINS, f"Domain '{domain}' not defined"

    def test_domains_have_description(self):
        """Each domain should have a description."""
        for domain, info in TOOL_DOMAINS.items():
            assert "description" in info, f"Domain '{domain}' missing description"
            assert info["description"], f"Domain '{domain}' has empty description"

    def test_domains_have_tools(self):
        """Each domain should have at least one tool."""
        for domain, info in TOOL_DOMAINS.items():
            assert "tools" in info, f"Domain '{domain}' missing tools list"
            assert len(info["tools"]) > 0, f"Domain '{domain}' has no tools"


class TestRouterIntentClassification:
    """Intent classification tests."""

    @pytest.mark.asyncio
    async def test_git_ops_query(self):
        """GitOps queries should route to GitOps domain."""
        router = get_router()
        result = await router.route_intent("Verify if the latest commit follows our guidelines")
        assert result["domain"] == "GitOps"
        assert result["confidence"] > 0.7
        assert "validate_commit_message" in result["suggested_tools"]

    @pytest.mark.asyncio
    async def test_product_owner_query(self):
        """ProductOwner queries should route to ProductOwner or similar domain."""
        router = get_router()
        result = await router.route_intent("Draft a feature spec for user authentication")
        # LLM routing is non-deterministic, accept ProductOwner or Coder with spec-related tools
        assert result["domain"] in ["ProductOwner", "Coder"]
        assert result["confidence"] > 0.6
        # Should have spec-related tools
        has_spec_tools = any("spec" in t or "feature" in t for t in result["suggested_tools"])
        assert has_spec_tools, f"Expected spec-related tools, got: {result['suggested_tools']}"

    @pytest.mark.asyncio
    async def test_coder_query(self):
        """Coder queries should route to Coder domain."""
        router = get_router()
        result = await router.route_intent("Create a new feature implementation for user login")
        assert result["domain"] == "Coder"
        assert result["confidence"] > 0.7
        assert "delegate_to_coder" in result["suggested_tools"]

    @pytest.mark.asyncio
    async def test_qa_query(self):
        """QA queries should route to QA domain."""
        router = get_router()
        result = await router.route_intent("Run the tests and analyze the failures")
        assert result["domain"] == "QA"
        assert result["confidence"] > 0.7
        assert "run_tests" in result["suggested_tools"]

    @pytest.mark.asyncio
    async def test_qa_code_review_query(self):
        """Code review queries should route to QA domain."""
        router = get_router()
        result = await router.route_intent("Review the staged changes for code quality")
        assert result["domain"] == "QA"
        assert result["confidence"] > 0.7
        assert "review_staged_changes" in result["suggested_tools"]

    @pytest.mark.asyncio
    async def test_memory_query(self):
        """Memory queries should route to Memory domain."""
        router = get_router()
        result = await router.route_intent("Check the current task status and context")
        assert result["domain"] == "Memory"
        assert result["confidence"] > 0.7
        assert "manage_context" in result["suggested_tools"]

    @pytest.mark.asyncio
    async def test_devops_query(self):
        """DevOps queries should route to DevOps domain."""
        router = get_router()
        result = await router.route_intent("Configure the Nix development environment")
        assert result["domain"] == "DevOps"
        assert result["confidence"] > 0.7
        assert "consult_specialist" in result["suggested_tools"]


class TestRouterSingleton:
    """Router singleton tests."""

    def test_get_router_returns_singleton(self):
        """get_router should return the same instance."""
        router1 = get_router()
        router2 = get_router()
        assert router1 is router2, "get_router should return singleton instance"


class TestRouterResponseFormat:
    """Response format tests."""

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        """Response should have domain, confidence, reasoning, and tools."""
        router = get_router()
        result = await router.route_intent("Fix a bug in the code")

        assert "domain" in result, "Response missing 'domain' field"
        assert "confidence" in result, "Response missing 'confidence' field"
        assert "reasoning" in result, "Response missing 'reasoning' field"
        assert "suggested_tools" in result, "Response missing 'suggested_tools' field"

    @pytest.mark.asyncio
    async def test_confidence_range(self):
        """Confidence should be between 0 and 1."""
        router = get_router()
        result = await router.route_intent("Do something with git")

        confidence = result["confidence"]
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of range [0, 1]"

    @pytest.mark.asyncio
    async def test_tools_from_domain(self):
        """Suggested tools should come from the matched domain."""
        router = get_router()
        result = await router.route_intent("Check git status")

        domain = result["domain"]
        if domain in TOOL_DOMAINS:
            expected_tools = TOOL_DOMAINS[domain]["tools"]
            for tool in result["suggested_tools"]:
                assert tool in expected_tools, f"Tool '{tool}' not in domain '{domain}'"
