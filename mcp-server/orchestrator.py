# mcp-server/orchestrator.py
import os
import sys
import asyncio
from mcp.server.fastmcp import FastMCP
from anthropic import AsyncAnthropic  # Key point: Import async client
from personas import PERSONAS         # Import separated prompts

# Initialize MCP Server
mcp = FastMCP("orchestrator-tools")

# Startup logs
sys.stderr.write(f"🚀 Orchestrator Server (Async) starting... PID: {os.getpid()}\n")

# Global Client initialization (connection pool reuse)
# AsyncAnthropic automatically handles connection pooling, avoiding new connections per call
api_key = os.environ.get("ANTHROPIC_API_KEY")
base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")

if not api_key:
    sys.stderr.write("⚠️ Warning: ANTHROPIC_API_KEY not found in environment.\n")

client = AsyncAnthropic(api_key=api_key, base_url=base_url)

@mcp.tool()
async def consult_specialist(role: str, query: str) -> str:
    """
    Consult a specialized AI expert for a specific domain task (Async Optimized).

    Args:
        role: The role to consult. Options: 'architect', 'platform_expert', 'devops_mlops', 'sre'.
        query: The specific question, code snippet, or design problem to analyze.
    """
    # 1. Validate inputs
    if role not in PERSONAS:
        return f"Error: Role '{role}' not found. Available roles: {list(PERSONAS.keys())}"
    
    if not api_key:
        return "Error: ANTHROPIC_API_KEY is missing."

    system_prompt = PERSONAS[role]

    try:
        # 2. Async API call (Non-blocking I/O)
        # The await here releases control, allowing the server to handle other requests concurrently (e.g., heartbeats, cancellations)
        response = await client.messages.create(
            model="MiniMax-M2.1",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": query}]
        )

        # 3. Process response
        final_text = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'text':
                final_text.append(block.text)
            elif hasattr(block, 'text'):
                final_text.append(block.text)

        if not final_text:
            return "Error: Model returned content but no text block found."

        return f"--- 🤖 Expert Opinion: {role.upper()} ---\n" + "\n".join(final_text)

    except Exception as e:
        sys.stderr.write(f"❌ API Call Error: {str(e)}\n")
        return f"Error consulting specialist: {str(e)}"

if __name__ == "__main__":
    mcp.run()
