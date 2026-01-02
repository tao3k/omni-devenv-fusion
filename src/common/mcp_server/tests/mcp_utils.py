# tests/mcp_utils.py
import json
import os
import subprocess
import sys
from pathlib import Path

# 默认查找路径（支持从根目录或 tests 目录运行）
CONFIG_CANDIDATES = [
    Path(".mcp.json").absolute(),
    Path("../.mcp.json").absolute(), # 如果在 tests/ 目录内运行
    Path(".claude/settings.json").absolute(),
]

def find_config():
    print("\n🔎 Searching for config files...")
    found = None
    for path in CONFIG_CANDIDATES:
        exists = path.exists()
        # 只打印简略信息，避免刷屏
        if exists and found is None:
            found = path
            print(f"   ✅ Found: {path}")
            break
    
    if not found:
        print("   ❌ No config file found in candidate paths.")
    return found

def read_json_rpc(process):
    """
    Reads the next JSON-RPC message from the server's stdout.
    """
    if process.poll() is not None:
        return None
        
    try:
        # 阻塞读取一行
        line = process.stdout.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        print(f"⚠️  Received non-JSON output: {line.strip()}")
        return None

def start_server_process(server_name="orchestrator"):
    """
    Parses config and starts the MCP server subprocess.
    Returns: (process, config_data) or (None, None)
    """
    config_path = find_config()
    if not config_path:
        return None, None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return None, None

    servers = config.get("mcpServers", {})
    if server_name not in servers:
        print(f"❌ No '{server_name}' field in config file.")
        return None, None

    server_conf = servers[server_name]
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
    return process, config
