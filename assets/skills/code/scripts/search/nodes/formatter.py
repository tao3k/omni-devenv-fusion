"""
Result Formatter - XML Output Generator

Generates structured XML output optimized for LLM consumption.
Includes interactive tags for guiding subsequent actions.
"""

from collections import defaultdict
from typing import List

from ..state import SearchGraphState, SearchResult


# Constants
MAX_RESULTS_BROAD = 20
MAX_RESULTS_FOCUSED = 10


def synthesize_results(state: SearchGraphState) -> dict:
    """Synthesize results from all search engines.

    Handles three scenarios:
    1. Too many results -> Return interactive refinement prompt
    2. Good results -> Return standard XML format
    3. No results -> Return suggestions
    """
    results = state.get("raw_results", [])
    query = state.get("query", "")

    if not results:
        return {
            "final_output": generate_no_results_xml(query),
            "needs_clarification": True,
            "clarification_prompt": f"No results found for '{query}'. Try different keywords or check if the knowledge base is indexed.",
        }

    # Remove duplicates (same file + line)
    unique = deduplicate_results(results)

    if len(unique) > MAX_RESULTS_BROAD:
        return {
            "final_output": generate_broad_results_xml(unique, query),
            "needs_clarification": True,
            "clarification_prompt": f"Found {len(unique)} matches. Consider refining your query.",
        }

    return {
        "final_output": generate_standard_xml(unique, query),
        "needs_clarification": False,
    }


def deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """Remove duplicate results based on file + line."""
    seen = set()
    unique = []
    for r in results:
        key = (r["file"], r["line"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def generate_standard_xml(results: List[SearchResult], query: str) -> str:
    """Generate standard XML for focused results."""
    items = []
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        escaped = escape_xml(r["content"][:300])
        items.append(f"""
    <item file="{r["file"]}" line="{r["line"]}" engine="{r["engine"]}" score="{r["score"]:.2f}">
        <context><![CDATA[{escaped}]]></context>
    </item>""")

    return f"""<search_results query="{query}" count="{len(results)}">
{"".join(items)}
</search_results>"""


def generate_broad_results_xml(results: List[SearchResult], query: str) -> str:
    """Generate interactive XML for broad results with clustering suggestions."""
    # Cluster by directory
    by_dir = defaultdict(list)
    for r in results:
        parts = r["file"].split("/")
        dir_key = parts[0] if parts else "."
        by_dir[dir_key].append(r)

    clusters = []
    for dir_name, items in sorted(by_dir.items())[:5]:
        clusters.append(f"""
        <cluster directory="{dir_name}" count="{len(items)}"/>""")

    return f"""<search_interaction type="broad_results">
    <summary>Found {len(results)} matches across {len(by_dir)} directories.</summary>
    <query>{query}</query>
    <top_directories>{"".join(clusters)}
    </top_directories>
    <suggestions>
        <action type="refine" strategy="class">Use 'class ClassName' to find specific definitions</action>
        <action type="refine" strategy="file">Limit to directory with: dir:directory_name</action>
        <action type="expand" strategy="context">Get more context around matches</action>
    </suggestions>
</search_interaction>"""


def generate_no_results_xml(query: str) -> str:
    """Generate XML for no results."""
    return f"""<search_interaction type="no_results">
    <query>{query}</query>
    <message>No matches found.</message>
    <suggestions>
        <action type="try_different">Try different keywords</action>
        <action type="check_index">Run 'omni knowledge ingest' to refresh the index</action>
        <action type="broader">Use broader terms like "authentication" instead of specific function names</action>
    </suggestions>
</search_interaction>"""


def escape_xml(text: str) -> str:
    """Basic XML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
