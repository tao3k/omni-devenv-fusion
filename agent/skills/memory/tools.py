"""
Memory Skill - The Hippocampus Interface

Role:
  Allows the Agent to semantically store and retrieve knowledge via ChromaDB.
  Replaces rigid file-based logging with fluid vector memory.

Philosophy:
  "Memory is the residue of thought." - Daniel Willingham
  This skill captures that residue in vector form for future retrieval.

Memory Path (from settings.yaml -> prj-spec):
  {git_toplevel}/.cache/{project_name}/.memory/

Tools (from prompts.md):
  - remember_insight: Store reusable learnings
  - log_episode: Log session actions
  - recall: Semantic search across memories
  - harvest_session_insight: Extract and store key learnings
"""
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

# =============================================================================
# Path Configuration (Configurable via settings.yaml)
# =============================================================================

def _get_git_toplevel() -> Path:
    """Get git toplevel directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def _get_memory_path() -> Path:
    """
    Get memory root path following prj-spec.
    Configurable via settings.yaml: memory.path
    Falls back to: {git_toplevel}/.cache/{project}/.memory/
    """
    # Use get_setting for configuration
    from common.mcp_core.settings import get_setting
    from common.mcp_core.gitops import get_project_root

    custom_path = get_setting("memory.path", "")
    if custom_path:
        return Path(custom_path)

    # Fallback to prj-spec structure
    project = "omni-dev-fusion"
    git_root = get_project_root()
    return git_root / ".cache" / project / "memory"


# Initialize path
MEMORY_ROOT = _get_memory_path()
DB_PATH = MEMORY_ROOT / "chroma_db"
DB_PATH.mkdir(parents=True, exist_ok=True)

try:
    client = chromadb.PersistentClient(path=str(DB_PATH))
    # Get or create collections
    episodic_mem = client.get_or_create_collection(name="episodic_memory")
    semantic_mem = client.get_or_create_collection(name="semantic_knowledge")
    CHROMA_AVAILABLE = True
except Exception as e:
    CHROMA_AVAILABLE = False
    client = None
    episodic_mem = None
    semantic_mem = None


def register(mcp: Any) -> None:
    """Register all memory tools."""

    @mcp.tool()
    async def remember_insight(content: str, domain: str = "general") -> str:
        """
        [Long-term Memory] Store a key insight, decision, or learning into ChromaDB.

        Use this when you've learned something reusable:
        - "Use scope 'nix' for flake changes"
        - "The project uses Conventional Commits"
        - "Always run 'just validate' before committing"

        Args:
            content: The insight to store (what you learned)
            domain: Category like "git", "nix", "architecture", "workflow"

        Returns:
            Confirmation message with stored content preview
        """
        if not CHROMA_AVAILABLE:
            return "❌ ChromaDB not available. Cannot store insight."

        timestamp = datetime.now().isoformat()

        # Store in semantic memory with domain as tag
        try:
            semantic_mem.add(
                documents=[content],
                metadatas=[
                    {"timestamp": timestamp, "domain": domain, "type": "insight"}
                ],
                ids=[f"insight_{timestamp}"]
            )
            return f"✅ Insight stored in Hippocampus:\n[Domain: {domain}]\n\"{content[:100]}...\""
        except Exception as e:
            return f"❌ Failed to store insight: {e}"

    @mcp.tool()
    async def log_episode(action: str, result: str, context: str = "") -> str:
        """
        [Short-term Memory] Log a significant action taken during the session.

        Use this for:
        - "Fixed bug in git skill"
        - "Refactored skill registry"
        - "Added new documentation"

        Args:
            action: What you did
            result: What happened (success/failure/observation)
            context: Optional context (file, function, etc.)

        Returns:
            Confirmation of logged episode
        """
        if not CHROMA_AVAILABLE:
            return "❌ ChromaDB not available. Cannot log episode."

        timestamp = datetime.now().isoformat()
        content = f"Action: {action}\nResult: {result}"
        if context:
            content += f"\nContext: {context}"

        try:
            episodic_mem.add(
                documents=[content],
                metadatas=[{"timestamp": timestamp, "type": "episode"}],
                ids=[f"epi_{timestamp}"]
            )
            return f"✅ Episode logged: {action[:50]}..."
        except Exception as e:
            return f"❌ Failed to log episode: {e}"

    @mcp.tool()
    async def recall(query: str, n_results: int = 3) -> str:
        """
        [Retrieval] Semantically search memory for relevant past experiences or rules.

        Examples:
        - recall("git commit message format")
        - recall("nixfmt error solution")
        - recall("how to add a new skill")

        Args:
            query: What you're looking for
            n_results: Number of results to return (default: 3)

        Returns:
            Relevant memories found, or "No relevant memories found"
        """
        if not CHROMA_AVAILABLE:
            return "❌ ChromaDB not available. Cannot recall memories."

        if not semantic_mem:
            return "No semantic memory available."

        try:
            results = semantic_mem.query(
                query_texts=[query],
                n_results=n_results
            )

            if not results['documents'][0]:
                return "🧠 No relevant memories found."

            memories = []
            for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                domain = meta.get('domain', 'unknown')
                memories.append(f"[{i+1}] [{domain}] {doc}")

            return f"🧠 **Hippocampus Recall**:\n" + "\n---\n".join(memories)
        except Exception as e:
            return f"❌ Recall failed: {e}"

    @mcp.tool()
    async def list_harvested_knowledge() -> str:
        """
        [Reflection] List all harvested insights stored in memory.

        Returns:
            Formatted list of all stored insights
        """
        if not CHROMA_AVAILABLE or not semantic_mem:
            return "No knowledge available."

        try:
            # Get all insights
            results = semantic_mem.get(where={"type": "insight"})

            if not results['documents']:
                return "No harvested knowledge yet."

            by_domain: Dict[str, List[str]] = {}
            for doc, meta in zip(results['documents'], results.get('metadatas', [])):
                domain = meta.get('domain', 'general')
                if domain not in by_domain:
                    by_domain[domain] = []
                by_domain[domain].append(doc)

            lines = ["🧠 **Harvested Knowledge**", ""]
            for domain, insights in by_domain.items():
                lines.append(f"### {domain.upper()}")
                for i, insight in enumerate(insights):
                    lines.append(f"  {i+1}. {insight[:80]}...")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"❌ Failed to list knowledge: {e}"

    @mcp.tool()
    async def harvest_session_insight(context_summary: str, files_changed: List[str] = None) -> str:
        """
        [Consolidation] Extract key learnings from current session and store in memory.

        Call this at the end of a significant session to capture:
        - What was accomplished
        - What was learned
        - What should be remembered

        Args:
            context_summary: Summary of what was done and learned
            files_changed: List of files that were modified

        Returns:
            Confirmation of harvested insights
        """
        if not CHROMA_AVAILABLE:
            return "❌ ChromaDB not available. Cannot harvest insights."

        timestamp = datetime.now().isoformat()

        # Create a comprehensive insight
        insight = f"Session at {timestamp}:\n{context_summary}"
        if files_changed:
            insight += f"\nFiles changed: {', '.join(files_changed)}"

        try:
            semantic_mem.add(
                documents=[insight],
                metadatas=[
                    {"timestamp": timestamp, "domain": "session", "type": "harvest"}
                ],
                ids=[f"harvest_{timestamp}"]
            )
            return f"✅ Session insight harvested and stored.\n\"{context_summary[:100]}...\""
        except Exception as e:
            return f"❌ Harvest failed: {e}"

    @mcp.tool()
    async def get_memory_stats() -> str:
        """
        [Diagnostics] Get statistics about stored memories.

        Returns:
            Count of episodic and semantic memories
        """
        if not CHROMA_AVAILABLE:
            return "❌ ChromaDB not available."

        stats = []
        try:
            if semantic_mem:
                semantic_count = semantic_mem.count()
                stats.append(f"Semantic memories (insights): {semantic_count}")

            if episodic_mem:
                episodic_count = episodic_mem.count()
                stats.append(f"Episodic memories (actions): {episodic_count}")

            return "🧠 **Memory Statistics**\n" + "\n".join(stats)
        except Exception as e:
            return f"❌ Stats failed: {e}"
