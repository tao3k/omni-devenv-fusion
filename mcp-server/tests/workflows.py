# tests/test_workflow.py
import json
import sys
from mcp_utils import start_server_process, read_json_rpc

def run_full_workflow():
    print("🚀 Starting End-to-End Workflow Test")
    process, _ = start_server_process("orchestrator")
    if not process:
        sys.exit(1)

    try:
        # === 1. Initialize ===
        init_msg = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize", 
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-workflow", "version": "1.0"}}
        }
        process.stdin.write(json.dumps(init_msg) + "\n")
        process.stdin.flush()
        read_json_rpc(process) # Skip init response
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()

        # === 2. 获取上下文 (Read Context) ===
        target_dir = "modules" # 假设我们要分析 modules 目录
        print(f"\n🤖 Step 1: Reading context from '{target_dir}'...")
        
        ctx_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_codebase_context",
                "arguments": {"target_dir": target_dir, "ignore_files": "**/*.lock"}
            }
        }
        process.stdin.write(json.dumps(ctx_req) + "\n")
        process.stdin.flush()

        ctx_resp = read_json_rpc(process)
        context_text = ""
        if ctx_resp and "result" in ctx_resp:
            context_text = ctx_resp["result"]["content"][0]["text"]
            print(f"✅ Context acquired ({len(context_text)} chars).")
        else:
            print(f"❌ Failed to get context: {ctx_resp}")
            return

        # === 3. 咨询专家 (Consult Architect) ===
        print("\n🤖 Step 2: Consulting 'Architect' with the code context...")
        
        # 截取前 8000 字符防止 Token 溢出（测试用）
        snippet = context_text[:8000] 
        query = (
            f"I have extracted the following Nix modules structure:\n\n{snippet}\n...\n(truncated)\n\n"
            "Question: Based on this, analyze the modularization strategy. Is it using standard NixOS module patterns?"
        )

        consult_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "consult_specialist",
                "arguments": {"role": "architect", "query": query}
            }
        }
        process.stdin.write(json.dumps(consult_req) + "\n")
        process.stdin.flush()

        print("⏳ Waiting for LLM response (this may take 5-10s)...")
        consult_resp = read_json_rpc(process)
        
        if consult_resp and "result" in consult_resp:
            print("\n💡 Expert Response:")
            print("="*60)
            print(consult_resp["result"]["content"][0]["text"])
            print("="*60)
        else:
            print(f"❌ Consultation Failed: {consult_resp}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    run_full_workflow()
