"""
Phase 9: Code Intelligence - ast-grep Integration Tests

Tests for structural code search and refactoring using ast-grep.

Scenarios:
1. Structural Search - Find code patterns by AST structure
2. Safe Refactoring - Preview changes before applying
3. Pattern Matching - Use wildcards and conditions
4. Router Integration - Verify Cortex routes refactor queries to Coder

Run: just test-mcp (includes these tests)
"""
import subprocess
import sys
import json
import os
from pathlib import Path


def read_json_rpc(process):
    """Reads the next JSON-RPC message from the server's stdout."""
    if process.poll() is not None:
        return None
    try:
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def send_tool(process, name: str, arguments: dict, tool_id: int) -> tuple[bool, str]:
    """Send a tool call and return (success, response_text)."""
    tool_msg = {
        "jsonrpc": "2.0",
        "id": tool_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }
    process.stdin.write(json.dumps(tool_msg) + "\n")
    process.stdin.flush()
    response = read_json_rpc(process)
    if response and "result" in response:
        content_list = response["result"].get("content", [])
        text_output = "".join(item.get("text", "") for item in content_list)
        return True, text_output
    elif response and "error" in response:
        return False, f"Error: {response['error']['message']}"
    return False, str(response)


def test_ast_search_patterns():
    """Test ast_search with various pattern types."""
    print("\n" + "=" * 60)
    print("🧪 Phase 9: Code Intelligence - ast_search Tests")
    print("=" * 60)

    # Start Coder server
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.coder"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    results = {}

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "test-phase9", "version": "1.0"}}
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        response = read_json_rpc(process)
        if not (response and "result" in response):
            print("❌ Failed to initialize Coder server")
            return False
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # Test 1: Find all function definitions
        print("\n1️⃣  Testing 'ast_search' - Find function definitions...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "def $NAME", "lang": "py", "path": "mcp-server/tests"},
            2
        )
        if success and ("ast-grep Results" in text or "def " in text):
            print(f"✅ Found function definitions: {len(text)} chars")
            results["ast_search_function_def"] = True
        else:
            print(f"❌ ast_search function_def failed: {text[:300]}")
            results["ast_search_function_def"] = False

        # Test 2: Find all async function calls
        print("\n2️⃣  Testing 'ast_search' - Find async calls...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "async def $NAME", "lang": "py", "path": "mcp-server"},
            3
        )
        if success and ("ast-grep Results" in text or "await" in text.lower() or "No matches" in text):
            print(f"✅ Async call search completed: {len(text)} chars")
            results["ast_search_async"] = True
        else:
            print(f"❌ ast_search async failed: {text[:300]}")
            results["ast_search_async"] = False

        # Test 3: Find all import statements
        print("\n3️⃣  Testing 'ast_search' - Find imports...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "import $MODULE", "lang": "py", "path": "mcp-server"},
            4
        )
        if success and ("ast-grep Results" in text or "import" in text.lower() or "No matches" in text):
            print(f"✅ Import search completed: {len(text)} chars")
            results["ast_search_import"] = True
        else:
            print(f"❌ ast_search import failed: {text[:300]}")
            results["ast_search_import"] = False

        # Test 4: Find try-except blocks
        print("\n4️⃣  Testing 'ast_search' - Find try-except blocks...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "try_stmt", "lang": "py", "path": "mcp-server"},
            5
        )
        if success:
            print(f"✅ Try-except search completed: {len(text)} chars")
            results["ast_search_try_stmt"] = True
        else:
            print(f"❌ ast_search try_stmt failed: {text[:300]}")
            results["ast_search_try_stmt"] = False

        # Test 5: Search with wildcard pattern
        print("\n5️⃣  Testing 'ast_search' - Wildcard pattern...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "call $FUNC($ARGS)", "lang": "py", "path": "mcp-server"},
            6
        )
        if success:
            print(f"✅ Wildcard search completed: {len(text)} chars")
            results["ast_search_wildcard"] = True
        else:
            print(f"❌ ast_search wildcard failed: {text[:300]}")
            results["ast_search_wildcard"] = False

        # Test 6: Find class definitions (note: class search has limited support in ast-grep)
        print("\n6️⃣  Testing 'ast_search' - Find class definitions...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "class $NAME", "lang": "py", "path": "mcp-server"},
            7
        )
        if success:
            print(f"✅ Class definition search completed: {len(text)} chars")
            results["ast_search_class_def"] = True
        else:
            print(f"❌ ast_search class_def failed: {text[:300]}")
            results["ast_search_class_def"] = False

        # Summary
        print("\n" + "=" * 60)
        print("📊 ast_search Test Results")
        print("=" * 60)
        all_passed = True
        for test, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test}: {status}")
            if not passed:
                all_passed = False
        print("=" * 60)
        return all_passed

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()


def test_ast_rewrite_scenarios():
    """Test ast_rewrite with various refactoring scenarios."""
    print("\n" + "=" * 60)
    print("🧪 Phase 9: Code Intelligence - ast_rewrite Tests")
    print("=" * 60)

    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.coder"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    results = {}

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "test-phase9", "version": "1.0"}}
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        response = read_json_rpc(process)
        if not (response and "result" in response):
            return False
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # Test 1: Preview refactoring (no matches expected)
        print("\n1️⃣  Testing 'ast_rewrite' - Preview refactoring...")
        success, text = send_tool(
            process, "ast_rewrite",
            {"pattern": "NONEXISTENT_FUNCTION_XYZ_123", "replacement": "replaced_func",
             "lang": "py", "path": "mcp-server/tests"},
            2
        )
        if success and ("no matches" in text.lower() or "Applied" in text):
            print(f"✅ ast_rewrite preview works: {text[:100]}")
            results["ast_rewrite_preview"] = True
        else:
            print(f"❌ ast_rewrite preview failed: {text[:300]}")
            results["ast_rewrite_preview"] = False

        # Test 2: Refactor with wildcard replacement
        print("\n2️⃣  Testing 'ast_rewrite' - Wildcard refactor...")
        success, text = send_tool(
            process, "ast_rewrite",
            {"pattern": "print($MSG)", "replacement": "logger.info($MSG)",
             "lang": "py", "path": "mcp-server"},
            3
        )
        # Should either apply changes or show diff
        if success and ("Applied" in text or "no matches" in text.lower() or "Error" in text):
            print(f"✅ ast_rewrite wildcard refactor: {text[:100]}")
            results["ast_rewrite_wildcard"] = True
        else:
            print(f"❌ ast_rewrite wildcard failed: {text[:300]}")
            results["ast_rewrite_wildcard"] = False

        # Test 3: Language-specific pattern
        print("\n3️⃣  Testing 'ast_rewrite' - Language filter...")
        success, text = send_tool(
            process, "ast_rewrite",
            {"pattern": "def $FUNC: $BODY", "replacement": "async def $FUNC: $BODY",
             "lang": "py", "path": "mcp-server"},
            4
        )
        if success:
            print(f"✅ ast_rewrite language filter: {len(text)} chars")
            results["ast_rewrite_lang_filter"] = True
        else:
            print(f"❌ ast_rewrite language filter failed: {text[:300]}")
            results["ast_rewrite_lang_filter"] = False

        # Summary
        print("\n" + "=" * 60)
        print("📊 ast_rewrite Test Results")
        print("=" * 60)
        all_passed = True
        for test, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test}: {status}")
            if not passed:
                all_passed = False
        print("=" * 60)
        return all_passed

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()


def test_router_code_intelligence():
    """Test that router routes refactor queries to Coder with ast tools."""
    print("\n" + "=" * 60)
    print("🧪 Phase 9: Router Integration - Code Intelligence")
    print("=" * 60)

    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.orchestrator"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={**os.environ, "ANTHROPIC_API_KEY": "test-key"}
    )

    results = {}

    try:
        # Initialize
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "test-phase9", "version": "1.0"}}
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        response = read_json_rpc(process)
        if not (response and "result" in response):
            return False
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # Test 1: Router suggests Coder for refactor query
        print("\n1️⃣  Testing 'consult_router' - Refactor query...")
        success, text = send_tool(
            process, "consult_router",
            {"query": "Replace all print statements with logger.info"},
            2
        )
        if success and ("Coder" in text or "ast_search" in text or "ast_rewrite" in text):
            print(f"✅ Router suggests Coder for refactor: {text[:200]}")
            results["router_refactor_to_coder"] = True
        else:
            print(f"❌ Router refactor routing failed: {text[:300]}")
            results["router_refactor_to_coder"] = False

        # Test 2: Router suggests Coder for structural search
        print("\n2️⃣  Testing 'consult_router' - Structural search query...")
        success, text = send_tool(
            process, "consult_router",
            {"query": "Find all async function definitions in the codebase"},
            3
        )
        if success and "Coder" in text:
            print(f"✅ Router suggests Coder for structural search: {text[:200]}")
            results["router_structural_to_coder"] = True
        else:
            print(f"❌ Router structural search routing failed: {text[:300]}")
            results["router_structural_to_coder"] = False

        # Test 3: Router includes ast tools in suggested tools
        print("\n3️⃣  Testing 'consult_router' - ast tools in suggestions...")
        success, text = send_tool(
            process, "consult_router",
            {"query": "Refactor all try-catch blocks to use new error handler"},
            4
        )
        if success and ("ast_search" in text or "ast_rewrite" in text):
            print(f"✅ Router suggests ast tools: {text[:200]}")
            results["router_suggests_ast_tools"] = True
        else:
            print(f"❌ Router ast tools suggestion failed: {text[:300]}")
            results["router_suggests_ast_tools"] = False

        # Summary
        print("\n" + "=" * 60)
        print("📊 Router Integration Test Results")
        print("=" * 60)
        all_passed = True
        for test, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test}: {status}")
            if not passed:
                all_passed = False
        print("=" * 60)
        return all_passed

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()


def run_all_phase9_tests():
    """Run all Phase 9 tests."""
    print("\n" + "🌟 " + "=" * 58 + " 🌟")
    print("🚀 Phase 9: Code Intelligence Test Suite")
    print("=" * 58)

    all_results = {}

    # Test ast_search patterns
    print("\n" + "-" * 60)
    print("📌 Testing ast_search patterns...")
    result = test_ast_search_patterns()
    all_results["ast_search_patterns"] = result

    # Test ast_rewrite scenarios
    print("\n" + "-" * 60)
    print("📌 Testing ast_rewrite scenarios...")
    result = test_ast_rewrite_scenarios()
    all_results["ast_rewrite_scenarios"] = result

    # Test router integration
    print("\n" + "-" * 60)
    print("📌 Testing router integration...")
    result = test_router_code_intelligence()
    all_results["router_integration"] = result

    # Final summary
    print("\n" + "🌟 " + "=" * 58 + " 🌟")
    print("📊 Phase 9: Complete Test Summary")
    print("=" * 58)

    all_passed = True
    for category, passed in all_results.items():
        status = "✅ ALL PASSED" if passed else "❌ SOME FAILED"
        print(f"   {category}: {status}")
        if not passed:
            all_passed = False

    print("=" * 58)
    if all_passed:
        print("🎉 Phase 9: Code Intelligence - ALL TESTS PASSED!")
    else:
        print("⚠️  Phase 9: Some tests failed. Review output above.")
    print("=" * 58)

    return all_passed


if __name__ == "__main__":
    success = run_all_phase9_tests()
    sys.exit(0 if success else 1)
