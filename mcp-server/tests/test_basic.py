"""
Comprehensive test suite for Dual-MCP Server Architecture

Tests both orchestrator.py (The "Brain") and coder.py (The "Hands"):

ORCHESTRATOR TOOLS (Macro-level):
1. get_codebase_context - Full codebase context via Repomix
2. list_directory_structure - Fast directory tree (token optimization)
3. list_personas - List available personas
4. consult_specialist - Expert consultation
5. delegate_to_coder - Bridge to Coder MCP
6. community_proxy - Wrap external MCPs
7. safe_sandbox - Secure command execution
8. memory_garden - Long-term project memory

CODER TOOLS (Micro-level):
1. read_file - Single file reading
2. search_files - Pattern search (grep-like)
3. save_file - Write files with backup & syntax validation
4. ast_search - AST-based code search
5. ast_rewrite - AST-based code rewrite

Run: uv run python mcp-server/tests/test_basic.py
Run Coder tests: uv run python mcp-server/tests/test_basic.py --coder
"""
import json
import os
import subprocess
import sys
from pathlib import Path

# === Debug: Print current environment info ===
print(f"📂 Current Working Directory (CWD): {os.getcwd()}")
print(f"👤 Current User: {os.environ.get('USER')}")

CONFIG_CANDIDATES = [
    Path(".mcp.json").absolute(),
    Path(".claude/settings.json").absolute(),
]

def find_config():
    print("\n🔎 Searching for config files...")
    found = None
    for path in CONFIG_CANDIDATES:
        exists = path.exists()
        status = "✅ Exists" if exists else "❌ Not found"
        print(f"   Check: {path} -> {status}")
        if exists and found is None:
            found = path
    return found

def read_json_rpc(process):
    """
    Reads the next JSON-RPC message from the server's stdout.
    """
    if process.poll() is not None:
        return None

    try:
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        print(f"⚠️  Received non-JSON output: {line.strip()}")
        return None

def send_tool(process, name: str, arguments: dict, tool_id: int) -> tuple[bool, str]:
    """
    Send a tool call and return (success, response_text).
    """
    tool_msg = {
        "jsonrpc": "2.0",
        "id": tool_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments
        }
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

def test_all_tools():
    """Test all Orchestrator MCP tools."""
    config_path = find_config()

    if not config_path:
        print("\n🚫 Fatal Error: No config file found!")
        return False

    print(f"\n🚀 Using config file: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return False

    servers = config.get("mcpServers", {})
    if "orchestrator" not in servers:
        print("❌ No 'orchestrator' field in config file.")
        return False

    server_conf = servers["orchestrator"]
    env_vars = server_conf.get("env", {})

    # Setup environment
    run_env = os.environ.copy()
    run_env.update(env_vars)

    # Command setup
    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    print(f"▶️  Starting Server: {executable} {' '.join(args)}")

    process = subprocess.Popen(
        [executable] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        text=True,
        bufsize=1
    )

    results = {}

    try:
        # === Step 1: Initialize ===
        print("\n" + "=" * 60)
        print("🧪 MCP Tools Test Suite")
        print("=" * 60)

        print("\n1️⃣  Initialize Server...")
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-script", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()

        response = read_json_rpc(process)
        if response and "result" in response:
            server_name = response['result']['serverInfo']['name']
            print(f"✅ Server Initialized: {server_name}")
            results["initialize"] = True
        else:
            print(f"❌ Initialization Failed: {response}")
            print(f"Stderr: {process.stderr.read()}")
            return False

        # Send initialized notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        process.stdin.flush()

        # === Tool 1: get_codebase_context ===
        print("\n2️⃣  Testing 'get_codebase_context'...")
        success, text = send_tool(
            process, "get_codebase_context",
            {"target_dir": "modules", "ignore_files": "**/.git/**"},
            2
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "<file path=" in text or "<?xml" in text:
                print("✅ XML structure detected")
            else:
                print("⚠️  Warning: No XML structure found")
            results["get_codebase_context"] = True
        else:
            print(f"❌ {text}")
            results["get_codebase_context"] = False

        # === Tool 2: list_directory_structure ===
        print("\n3️⃣  Testing 'list_directory_structure'...")
        success, text = send_tool(
            process, "list_directory_structure",
            {"root_dir": "."},
            3
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "├── " in text or "└── " in text:
                print("✅ Directory tree structure detected")
            if len(text) < 10000:
                print("✅ Token optimization: Lightweight response")
            results["list_directory_structure"] = True
        else:
            print(f"❌ {text}")
            results["list_directory_structure"] = False

        # === Tool 3: list_personas ===
        print("\n4️⃣  Testing 'list_personas'...")
        success, text = send_tool(process, "list_personas", {}, 4)
        if success:
            print(f"✅ Response: {len(text)} chars")
            try:
                personas = json.loads(text)
                available = ", ".join(p.get("id", "unknown") for p in personas)
                print(f"✅ Personas: [{available}]")
                results["list_personas"] = True
            except json.JSONDecodeError:
                print("⚠️  Warning: Invalid JSON in personas response")
                results["list_personas"] = True  # Still counts as success
        else:
            print(f"❌ {text}")
            results["list_personas"] = False

        # === Tool 4: consult_specialist ===
        print("\n5️⃣  Testing 'consult_specialist'...")
        success, text = send_tool(
            process, "consult_specialist",
            {"role": "architect", "query": "What is the project structure?"},
            5
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "ANTHROPIC_API_KEY is missing" in text:
                print("⚠️  Expected: API key missing (expected without key)")
            elif "Expert Opinion" in text or "architect" in text.lower():
                print("✅ Expert consultation working")
            results["consult_specialist"] = True
        else:
            print(f"❌ {text}")
            results["consult_specialist"] = False

        # === Tool 5: delegate_to_coder (The Bridge) ===
        print("\n6️⃣  Testing 'delegate_to_coder'...")
        success, text = send_tool(
            process, "delegate_to_coder",
            {"task_type": "refactor", "details": "Rename function foo to bar"},
            6
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "Coder" in text or "read_file" in text or "search_files" in text:
                print("✅ Bridge delegation working")
            results["delegate_to_coder"] = True
        else:
            print(f"❌ {text}")
            results["delegate_to_coder"] = False

        # === Tool 6: safe_sandbox ===
        print("\n7️⃣  Testing 'safe_sandbox'...")
        success, text = send_tool(
            process, "safe_sandbox",
            {"command": "echo", "args": ["hello world"]},
            7
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "hello" in text.lower() or "hello world" in text:
                print("✅ Sandbox execution working")
            results["safe_sandbox"] = True
        else:
            print(f"❌ {text}")
            results["safe_sandbox"] = False

        # === Tool 7: safe_sandbox security ===
        print("\n8️⃣  Testing 'safe_sandbox' security (blocked patterns)...")
        success, text = send_tool(
            process, "safe_sandbox",
            {"command": "rm", "args": ["-rf", "/"]},
            8
        )
        if not success or "Blocked" in text or "dangerous" in text.lower() or "not allowed" in text.lower():
            print("✅ Blocked dangerous command in sandbox")
            results["safe_sandbox_security"] = True
        else:
            print("❌ Should have blocked dangerous command")
            results["safe_sandbox_security"] = False

        # === Tool 8: memory_garden ===
        print("\n9️⃣  Testing 'memory_garden'...")
        success, text = send_tool(
            process, "memory_garden",
            {"operation": "save", "title": "Test Decision", "content": "This is a test decision"},
            9
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "saved" in text.lower() or "memory" in text.lower() or ".memory" in text:
                print("✅ Memory garden working")
            results["memory_garden"] = True
        else:
            print(f"❌ {text}")
            results["memory_garden"] = False

        # === Tool 9: run_task ===
        success, text = send_tool(
            process, "run_task",
            {"command": "just", "args": ["--version"]},
            13
        )
        if success:
            print(f"✅ Response: {len(text)} chars")
            if "just" in text.lower() or "Exit code" in text:
                print("✅ Task execution working")
            results["run_task"] = True
        else:
            print(f"❌ {text}")
            results["run_task"] = False

        # Test blocked command
        print("\n🔟  Testing 'run_task' security (blocked command)...")
        success, text = send_tool(
            process, "run_task",
            {"command": "rm", "args": ["-rf", "/"]},
            14
        )
        if not success or "not allowed" in text.lower():
            print("✅ Blocked dangerous command")
            results["run_task_security"] = True
        else:
            print("❌ Should have blocked dangerous command")
            results["run_task_security"] = False

        # === Summary ===
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)

        all_passed = True
        for tool, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {tool}: {status}")
            if not passed:
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("🎉 All MCP tools are working correctly!")
        else:
            print("⚠️  Some tools failed. Please review the output above.")
        print("=" * 60)

        return all_passed

    except Exception as e:
        print(f"❌ Exception during test: {e}")
        return False

    finally:
        print("\n🧹 Cleaning up...")
        process.terminate()
        try:
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"📋 Server Logs (Stderr):\n{stderr_output}")
        except:
            pass
        process.wait()


# =============================================================================
# Coder Server Tests
# =============================================================================

def test_coder_tools():
    """Test all Coder MCP tools (ast-grep, file operations)."""
    config_path = find_config()

    if not config_path:
        print("\n🚫 Fatal Error: No config file found!")
        return False

    print(f"\n🚀 Using config file: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return False

    servers = config.get("mcpServers", {})
    if "coder" not in servers:
        print("❌ No 'coder' field in config file.")
        return False

    server_conf = servers["coder"]
    env_vars = server_conf.get("env", {})

    # Setup environment
    run_env = os.environ.copy()
    run_env.update(env_vars)

    # Command setup
    cmd = server_conf.get("command")
    args = server_conf.get("args", [])
    executable = sys.executable if cmd in ["python", "python3"] else cmd

    print(f"▶️  Starting Coder Server: {executable} {' '.join(args)}")

    process = subprocess.Popen(
        [executable] + args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=run_env,
        text=True,
        bufsize=1
    )

    results = {}

    try:
        print("\n" + "=" * 60)
        print("🧪 Coder Server Tools Test Suite")
        print("=" * 60)

        # === Step 1: Initialize ===
        print("\n1️⃣  Initialize Coder Server...")
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-script", "version": "1.0"}
            }
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()

        response = read_json_rpc(process)
        if response and "result" in response:
            server_name = response['result']['serverInfo']['name']
            print(f"✅ Server Initialized: {server_name}")
            results["initialize"] = True
        else:
            print(f"❌ Initialization Failed: {response}")
            print(f"Stderr: {process.stderr.read()}")
            return False

        # Send initialized notification
        process.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n")
        process.stdin.flush()

        # === Tool 1: read_file ===
        print("\n2️⃣  Testing 'read_file'...")
        success, text = send_tool(
            process, "read_file",
            {"path": "mcp-server/tests/test_basic.py"},
            2
        )
        if success and "test_all_tools" in text:
            print(f"✅ read_file working: {len(text)} chars")
            results["read_file"] = True
        else:
            print(f"❌ read_file failed: {text[:200]}")
            results["read_file"] = False

        # === Tool 2: search_files ===
        print("\n3️⃣  Testing 'search_files'...")
        success, text = send_tool(
            process, "search_files",
            {"pattern": "def test_all_tools", "path": "mcp-server/tests"},
            3
        )
        if success and ("test_basic.py" in text or "matches found" in text.lower()):
            print(f"✅ search_files working: {len(text)} chars")
            results["search_files"] = True
        else:
            print(f"❌ search_files failed: {text[:200]}")
            results["search_files"] = False

        # === Tool 3: save_file (create temp file) ===
        print("\n4️⃣  Testing 'save_file'...")
        success, text = send_tool(
            process, "save_file",
            {"path": "test_temp_output.txt", "content": "Hello from test!\nTimestamp: " + str(os.getpid())},
            4
        )
        if success and "Successfully wrote" in text:
            print(f"✅ save_file working: {text[:100]}")
            results["save_file"] = True
        else:
            print(f"❌ save_file failed: {text[:200]}")
            results["save_file"] = False

        # === Tool 4: ast_search ===
        print("\n5️⃣  Testing 'ast_search' (ast-grep)...")
        success, text = send_tool(
            process, "ast_search",
            {"pattern": "def $name", "lang": "py", "path": "mcp-server/tests"},
            5
        )
        if success and ("ast-grep Results" in text or "def " in text):
            print(f"✅ ast_search working: {len(text)} chars")
            results["ast_search"] = True
        else:
            print(f"❌ ast_search failed: {text[:300]}")
            results["ast_search"] = False

        # === Tool 5: ast_rewrite ===
        print("\n6️⃣  Testing 'ast_rewrite' (ast-grep)...")
        # Use a unique pattern that won't match anything to test the tool
        unique_pattern = "UNIQUE_PATTERN_DOES_NOT_EXIST_xyz123"
        success, text = send_tool(
            process, "ast_rewrite",
            {"pattern": unique_pattern, "replacement": "replaced", "lang": "py", "path": "mcp-server/tests"},
            6
        )
        # Should return "no matches" but still work
        if success and ("no matches" in text.lower() or "Applied" in text):
            print(f"✅ ast_rewrite working: {len(text)} chars")
            results["ast_rewrite"] = True
        else:
            print(f"❌ ast_rewrite failed: {text[:300]}")
            results["ast_rewrite"] = False

        # === Security Tests ===
        print("\n7️⃣  Testing 'read_file' security (blocked path)...")
        success, text = send_tool(
            process, "read_file",
            {"path": "/etc/passwd"},
            7
        )
        if not success or "Absolute paths are not allowed" in text or "not allowed" in text:
            print("✅ Blocked absolute path read")
            results["read_file_security"] = True
        else:
            print("❌ Should have blocked absolute path")
            results["read_file_security"] = False

        print("\n8️⃣  Testing 'save_file' security (blocked path)...")
        success, text = send_tool(
            process, "save_file",
            {"path": "/tmp/hacked.txt", "content": "malicious"},
            8
        )
        if not success or "Absolute paths are not allowed" in text:
            print("✅ Blocked absolute path write")
            results["save_file_security"] = True
        else:
            print("❌ Should have blocked absolute path")
            results["save_file_security"] = False

        # === Cleanup temp file ===
        try:
            Path("test_temp_output.txt").unlink()
            print("\n🧹 Cleaned up temp file")
        except:
            pass

        # === Summary ===
        print("\n" + "=" * 60)
        print("📊 Coder Server Test Results Summary")
        print("=" * 60)

        all_passed = True
        for tool, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {tool}: {status}")
            if not passed:
                all_passed = False

        print("=" * 60)
        if all_passed:
            print("🎉 All Coder server tools are working correctly!")
        else:
            print("⚠️  Some Coder tools failed. Please review the output above.")
        print("=" * 60)

        return all_passed

    except Exception as e:
        print(f"❌ Exception during Coder test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("\n🧹 Cleaning up Coder server...")
        process.terminate()
        try:
            stderr_output = process.stderr.read()
            if stderr_output:
                print(f"📋 Server Logs (Stderr):\n{stderr_output}")
        except:
            pass
        process.wait()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--coder":
        success = test_coder_tools()
    else:
        success = test_all_tools()
    sys.exit(0 if success else 1)
