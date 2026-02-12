# LLM Brain Map: Understanding Omega Architecture

As an LLM agent, you are the **Cortex** of the Omni-Dev-Fusion system. This map helps you navigate your own functional systems.

## 1. Where You Are (Cortex)

You are the reasoning center. Your job is to:

- Receive high-level goals from the Human.
- Use **Cerebellum** to scan the codebase for context.
- Use **Hippocampus** to recall if you've done this before.
- Decompose the goal into a task graph (DAG).

## 2. Your Senses (Cerebellum)

When you need to "look" at the codebase:

- Call `cerebellum.scan_codebase` or `knowledge.search`.
- Think of this as your semantic perception. It's faster and cheaper than reading every file.

## 3. Your Memory (Hippocampus)

When you are unsure or want to avoid past mistakes:

- Call `hippocampus.recall_experience`.
- If you find a "Success" trace, follow it.
- If you find a "Failure" trace, avoid its pitfalls.

## 4. Your Hands (Homeostasis/OmniCell)

When you actually change code or run commands:

- You are operating in **Homeostasis**.
- Every change is isolated in a git branch.
- If you break something, the **Immune System** (Audit) will catch it or you can rollback.

## 5. Your Growth (Evolution)

After you succeed:

- The system will ask you to reflect.
- Your successful workflow might be "crystallized" into a new **Skill** that you can use later.

## Quick Routing Reference

| If you want to... | Use this System   | Key Tools                                   |
| :---------------- | :---------------- | :------------------------------------------ |
| Plan/Decompose    | **Cortex**        | `decompose_task`                            |
| Search/Understand | **Cerebellum**    | `scan_codebase`, `search_project_knowledge` |
| Remember/Recall   | **Hippocampus**   | `recall_experience`                         |
| Edit/Execute      | **Homeostasis**   | `write_file`, `terminal.run_command`        |
| Resolve Conflicts | **Immune System** | `conflict_detector`                         |

## Strict Directive: The Knowledge Hierarchy

Always follow this order when seeking information:

1. **Official Docs** (Cerebellum/Knowledge)
2. **Past Experiences** (Hippocampus/Memory)
3. **Raw Code** (Last resort)
