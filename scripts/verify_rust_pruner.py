"""
scripts/verify_rust_pruner.py
验证 Rust-Powered Context Pruner 的功能与性能。
"""

import time
from omni.agent.core.context.pruner import ContextPruner, PruningConfig


def generate_massive_history(turns: int = 10, output_size: int = 5000):
    """生成模拟的长对话历史"""
    messages = []
    messages.append({"role": "system", "content": "You are Omni. Solve the task."})

    for i in range(turns):
        # User input
        messages.append({"role": "user", "content": f"Step {i}: Run analysis."})
        # Assistant thought
        messages.append({"role": "assistant", "content": f"Checking step {i}..."})
        # Tool output (Huge data!)
        large_output = f"Log data line {i}..." * (output_size // 20)
        messages.append({"role": "tool", "content": large_output})

    return messages


def main():
    print("🚀 Initializing Rust Context Pruner...")
    # 配置：保留最近 2 轮，工具输出限制为 200 字符
    config = PruningConfig(retained_turns=2, max_tool_output=200)
    pruner = ContextPruner(config=config)

    # 1. 模拟 20 轮对话，每轮工具输出 10KB
    print("📦 Generating mock history (20 turns, heavy logs)...")
    history = generate_massive_history(turns=20, output_size=10000)

    print(f"📊 Original Message Count: {len(history)}")
    original_size = sum(len(str(m["content"])) for m in history)
    print(f"💾 Original Size (approx): {original_size / 1024:.2f} KB")

    # 2. 执行压缩 (计时)
    print("✂️  Compressing via Rust...")
    start_time = time.perf_counter()

    compressed = pruner.prune(history)

    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000

    # 3. 验证结果
    print("-" * 40)
    print(f"⚡ Time Taken: {duration_ms:.4f} ms")
    print(f"📊 Compressed Message Count: {len(compressed)}")
    compressed_size = sum(len(str(m["content"])) for m in compressed)
    print(f"💾 Compressed Size (approx): {compressed_size / 1024:.2f} KB")
    print(f"📉 Compression Ratio: {compressed_size / original_size * 100:.1f}%")

    # 检查 System Prompt 是否还在
    if compressed and compressed[0]["role"] == "system":
        print("✅ System prompt preserved.")
    else:
        print("❌ System prompt lost!")

    # 检查旧的消息是否被压缩
    # 我们保留最后 2 轮 (6条消息) + System (1) = 7条左右
    # 也就是前面的 Tool 消息应该被截断
    tool_msgs = [m for m in compressed if m["role"] == "tool"]
    if tool_msgs:
        old_tool_msg = tool_msgs[0]
        content = str(old_tool_msg["content"])
        if "truncated" in content.lower() or "[compressed]" in content.lower():
            print("✅ Old tool outputs successfully truncated.")
        else:
            print(f"⚠️  Tool output length: {len(content)} chars")
            print(f"   Content preview: {content[:200]}...")

    print("-" * 40)
    print("Preview of pruned message:")
    if tool_msgs:
        print(tool_msgs[0]["content"][:300])


if __name__ == "__main__":
    main()
