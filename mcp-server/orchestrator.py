import os
import sys
from mcp.server.fastmcp import FastMCP
from anthropic import Anthropic

# Initialize MCP Server
mcp = FastMCP("orchestrator-tools")

# Startup logs (print to stderr for debugging, won't affect stdout MCP protocol)
sys.stderr.write(f"🚀 Orchestrator Server starting... PID: {os.getpid()}\n")
sys.stderr.flush()

# === Define Expert Personas ===
PERSONAS = {
    "architect": """
You are a Principal Software Architect.
Your focus is on high-level system design, domain boundaries, and technical trade-offs.
- Analyze requirements from a strategic perspective.
- Ensure loose coupling and high cohesion.
- Make decisions on technology stacks and architectural patterns (Microservices, Monolith, Serverless).
- Do not get bogged down in implementation details unless necessary for the design.
""",

    "platform_expert": """
You are a Platform Engineering Expert.
Your goal is to build the Internal Developer Platform (IDP) and underlying infrastructure.
- Focus on Infrastructure as Code (Nix, Terraform, Crossplane).
- Expertise in Kubernetes, Containerization, and Cloud-Native ecosystems.
- Prioritize developer experience (DX) and self-service capabilities.
- Ensure the underlying compute/storage/networking is abstracted correctly.
""",

    "devops_mlops": """
You are a DevOps & MLOps Expert.
Your focus is on the automation of the software and data lifecycles.
- Design CI/CD pipelines (GitHub Actions, Lefthook).
- Ensure reproducible builds (Nix is your primary tool here).
- For MLOps: Focus on model training pipelines, experiment tracking, and model serving.
- Automate everything: testing, linting, packaging, and deployment.
""",

    "sre": """
You are a Site Reliability Engineer (SRE).
Your priority is reliability, scalability, and observability.
- Think in terms of SLIs, SLOs, and Error Budgets.
- Design for failure: circuit breakers, retries, rate limiting.
- Focus on Observability: Logging, Metrics, Tracing (Prometheus, Grafana, OpenTelemetry).
- Review code for potential performance bottlenecks and security risks.
"""
}

@mcp.tool()
def consult_specialist(role: str, query: str) -> str:
    """
    Consult a specialized AI expert for a specific domain task.

    Args:
        role: The role to consult. Options: 'architect', 'platform_expert', 'devops_mlops', 'sre'.
        query: The specific question, code snippet, or design problem to analyze.
    """
    # 1. Get environment variables (Lazy Loading)
    # This allows the server to start without a Key and only error here for easier debugging
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")

    if not api_key:
        sys.stderr.write("❌ Error: ANTHROPIC_API_KEY is missing.\n")
        return "Error: ANTHROPIC_API_KEY is missing in environment variables. Please check your MCP config or .env file."

    # 2. Initialize client
    try:
        client = Anthropic(api_key=api_key, base_url=base_url)
    except Exception as e:
        return f"Error initializing Anthropic client: {str(e)}"

    # 3. Validate role
    if role not in PERSONAS:
        return f"Error: Role '{role}' not found. Available roles: {list(PERSONAS.keys())}"

    system_prompt = PERSONAS[role]

    try:
        # 4. Call API (using Minimax model)
        # Note: Minimax model may return ThinkingBlock, needs special handling
        response = client.messages.create(
            model="MiniMax-M2.1", # Ensure correct model ID is used
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": query}]
        )

        # 5. Process response (core fix: filter ThinkingBlock)
        final_text = []
        for block in response.content:
            # Check block type, only extract text
            if hasattr(block, 'type') and block.type == 'text':
                final_text.append(block.text)
            elif hasattr(block, 'text'): # Double check
                final_text.append(block.text)
            # If it's a thinking block (block.type == 'thinking'), it will be ignored here

        if not final_text:
            return "Error: Model returned content but no text block found (possibly only thinking blocks)."

        return f"--- 🤖 Expert Opinion: {role.upper()} ---\n" + "\n".join(final_text)

    except Exception as e:
        sys.stderr.write(f"❌ API Call Error: {str(e)}\n")
        return f"Error consulting specialist: {str(e)}"

if __name__ == "__main__":
    # Use mcp.run() to start the Server
    mcp.run()
