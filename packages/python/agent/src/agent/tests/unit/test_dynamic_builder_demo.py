"""
DynamicGraphBuilder Demo: Update & Commit Scenario

This script demonstrates the Functional Graph Construction approach
for the "Update Docs -> Smart Commit" workflow.

Run: uv run python packages/python/agent/src/agent/tests/unit/test_dynamic_builder_demo.py
"""

from unittest.mock import AsyncMock, MagicMock

from agent.core.orchestrator.builder import DynamicGraphBuilder
from agent.core.state import GraphState


def create_mock_skill_manager():
    """Create a mock SkillManager for demonstration."""
    manager = MagicMock()
    manager.run = AsyncMock(return_value={"content": "test content"})
    return manager


def demo_update_commit_workflow():
    """Demonstrate the Update & Commit workflow graph."""
    print("=" * 60)
    print("DynamicGraphBuilder Demo: Update & Commit Workflow")
    print("=" * 60)

    mock_skill_manager = create_mock_skill_manager()
    builder = DynamicGraphBuilder(mock_skill_manager)

    # =====================================================================
    # Node 1: Read file (filesystem.read_file)
    # =====================================================================
    builder.add_skill_node(
        "read_file",
        "filesystem",
        "read_file",
        fixed_args={"path": "docs/index.md"},
        state_output={"content": "file_content"},
    )
    print("[1] Added node: read_file (filesystem.read_file)")

    # =====================================================================
    # Node 2: Generate update (LLM processing)
    # =====================================================================
    builder.add_llm_node(
        "generate_update",
        prompt_template="""
Original Content:
{{file_content}}

Instruction: Update the status to "Omni-Dev 1.0 is ready."

Output the FULL updated file content only.
        """,
        model="default",
        state_output="new_content",
    )
    print("[2] Added node: generate_update (LLM)")

    # =====================================================================
    # Node 3: Write file (filesystem.write_file)
    # =====================================================================
    builder.add_skill_node(
        "write_file",
        "filesystem",
        "write_file",
        state_input={"content": "new_content"},
    )
    print("[3] Added node: write_file (filesystem.write_file)")

    # =====================================================================
    # Node 4: Git prepare (git.stage_and_scan)
    # =====================================================================
    builder.add_skill_node(
        "git_prepare",
        "git",
        "stage_and_scan",
        state_output={"diff_preview": "diff"},
    )
    print("[4] Added node: git_prepare (git.stage_and_scan)")

    # =====================================================================
    # Node 5: Git commit (git.commit) - INTERRUPT POINT
    # =====================================================================
    builder.add_skill_node(
        "git_commit",
        "git",
        "commit",
        fixed_args={"message": "docs: update index with 1.0 status"},
    )
    print("[5] Added node: git_commit (git.commit) - INTERRUPT POINT")

    # =====================================================================
    # Define sequence: read → generate → write → git_prepare → git_commit
    # =====================================================================
    builder.add_sequence(
        "read_file",
        "generate_update",
        "write_file",
        "git_prepare",
        "git_commit",
    )
    builder.set_entry_point("read_file")

    print("\n[+] Graph structure defined")

    # =====================================================================
    # Compile with interrupt_before (Human-in-the-Loop)
    # =====================================================================
    graph = builder.compile(interrupt_before=["git_commit"])
    print("[+] Graph compiled with interrupt_before=['git_commit']")

    # =====================================================================
    # Visualize the graph
    # =====================================================================
    print("\n" + "=" * 60)
    print("Mermaid Diagram:")
    print("=" * 60)
    mermaid = builder.visualize()
    print(mermaid)

    # =====================================================================
    # Summary
    # =====================================================================
    print("=" * 60)
    print("Workflow Summary:")
    print("=" * 60)
    print(f"  Total nodes: {len(builder.nodes)}")
    print(f"  Nodes: {list(builder.nodes.keys())}")
    print(f"  Entry point: {builder._entry_point}")
    print(f"  Interrupt before: git_commit")
    print()
    print("Expected flow:")
    print("  1. read_file → reads docs/index.md")
    print("  2. generate_update → LLM generates updated content")
    print("  3. write_file → writes updated content")
    print("  4. git_prepare → stages files and scans for issues")
    print("  5. [PAUSE] → User confirms 'yes' to commit")
    print("  6. git_commit → Executes the commit")

    return graph, builder


def demo_conditional_workflow():
    """Demonstrate conditional workflow based on security scan."""
    print("\n" + "=" * 60)
    print("Conditional Workflow Demo: Security Scan")
    print("=" * 60)

    mock_skill_manager = create_mock_skill_manager()
    builder = DynamicGraphBuilder(mock_skill_manager)

    # Node 1: Git prepare (returns security_issues)
    builder.add_skill_node(
        "git_prepare",
        "git",
        "stage_and_scan",
        state_output={"security_issues": "security_issues"},
    )

    # Node 2: Commit (safe path)
    builder.add_skill_node("git_commit", "git", "commit")

    # Node 3: Security alert (unsafe path)
    builder.add_function_node(
        "security_alert",
        lambda state: {"workflow_state": {"alert": "Security issues detected!"}},
    )

    builder.set_entry_point("git_prepare")

    # Conditional edge based on security scan result
    builder.add_conditional_edges(
        "git_prepare",
        lambda state: "security_alert" if state.get("security_issues") else "git_commit",
        {"security_alert": "security_alert", "git_commit": "git_commit"},
    )

    from langgraph.graph import END

    builder.add_edge("git_commit", END)
    builder.add_edge("security_alert", END)

    graph = builder.compile()

    print(f"  Total nodes: {len(builder.nodes)}")
    print(f"  Nodes: {list(builder.nodes.keys())}")
    print(f"  Conditional routing: git_prepare → (security_issues ? security_alert : git_commit)")
    print("\n" + builder.visualize())

    return graph


if __name__ == "__main__":
    # Run demos
    graph1, builder1 = demo_update_commit_workflow()
    graph2 = demo_conditional_workflow()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
