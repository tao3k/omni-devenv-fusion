# Aider vs Omni ReAct: Model Interaction and Shell Execution

> Analysis of how Aider interacts with the LLM (especially shell/bash) and what it implies for our loop/reaction system.

## 1. How Aider Interacts with the Model

### 1.1 Message Construction (Layered Context)

Aider builds **layered messages** before each LLM call:

| Layer           | Content                          | Purpose                 |
| --------------- | -------------------------------- | ----------------------- |
| System          | Main system prompt + reminder    | Persona and rules       |
| Repo map        | Repository structure (selective) | Codebase overview       |
| Read-only files | Reference files (e.g. docs)      | Context without editing |
| Chat files      | Files being edited (with fences) | Current working set     |
| Current         | User message + history           | Conversation            |

File content uses **configurable fences** (triple backticks, `<source>`, etc.) so the model sees a consistent, parseable format. Token budget is managed (e.g. summarization when history is long).

**Implication for us**: Our Observe phase should also stack context in a clear order (system → knowledge/memory → task → tool results). Explicit layers help the model separate “rules” from “current state” from “last tool output”.

### 1.2 Response Parsing (Edits, Not Tools)

Aider does **not** use LLM tool-calling for edits. The model returns **plain text** with embedded edit blocks:

- **EditBlock**: `SEARCH/REPLACE` blocks with original and updated snippets.
- **Unified diff**: Fenced ```diff blocks.

Parsing uses **fallbacks**: exact match → whitespace-tolerant → fuzzy (e.g. 0.8 similarity). Failed edits return “Did you mean…”-style feedback. So the model gets **structured failure feedback** and can correct.

**Implication for us**: For tools we do use tool_calls or parsed JSON/XML; for “free-form” model output (e.g. suggested commands in prose), we already use multiple extraction strategies. Keeping **several parse strategies** (JSON → XML → ```bash → “I’ll run:”) is the right idea.

### 1.3 Shell / “Bash” in Aider: User-Triggered, Template Feedback

Aider does **not** let the model call the shell by itself. Commands are run only when the **user** does:

- `/run <command>` — run and optionally add output to chat.
- `!<command>` — same as `/run`.

Flow:

1. **Run**: `Commands.cmd_run()` → `run_cmd(args, cwd=self.coder.root)` → `(exit_status, combined_output)`.
2. **Decide whether to add to chat**: User is asked “Add Xk tokens of output?” (or for `/test`, add automatically if exit ≠ 0).
3. **Inject as user message**:  
   `prompts.run_output.format(command=args, output=combined_output)`  
   → `"I ran this command:\n\n{command}\n\nAnd got this output:\n\n{output}"`.
4. **Keep alternation**: They append a synthetic assistant message `"Ok."` so the next turn stays user/assistant/user/assistant.

So the model **sees** command and output in a **fixed template** and continues reasoning in the next turn. The “bash” interaction is **human-in-the-loop**: the model suggests, the user runs, the result is formatted and fed back.

**Implication for us**: We **automate** execution (parse model response → run via OmniCell → inject result). To make that feel like Aider’s “clear feedback”, we should:

- Format tool/shell results in a **stable, readable template** (e.g. “Command: …\nExit code: …\nOutput: …”).
- Include **exit code** (and stderr when relevant) so the model can branch on success/failure.

## 2. How Our ReAct Loop Differs

| Aspect                | Aider                                    | Omni ReAct                                                |
| --------------------- | ---------------------------------------- | --------------------------------------------------------- |
| Tool/shell invocation | User runs `/run` or `!`                  | Model output parsed → auto-execute                        |
| Edit application      | Parse SEARCH/REPLACE or diff from text   | N/A (we use tools for file edits)                         |
| Tool result format    | `run_output` template (command + output) | `[Tool: name] Result: ...` (generic)                      |
| Loop control          | User keeps chatting or runs commands     | Explicit exit token (e.g. EXIT_LOOP_NOW) + max_tool_calls |
| Stagnation            | N/A (user in loop)                       | Loop detection (hash), consecutive-error abort            |

We already do:

- **Multi-format command extraction** (OpenAI JSON, XML, ```bash, “I’ll run:”, %cmd%, $ cmd).
- **Execution** via OmniCell and **injection** of results as user message, then continue loop.
- **Loop detection** (tool call hash) and **stagnation** (max consecutive errors).

What we can improve from Aider:

1. **Structured tool result template** for shell (and optionally other tools): e.g. “Command: {command}\nExit code: {code}\nStdout:\n{stdout}\nStderr:\n{stderr}” so the model always sees the same shape.
2. **Explicit exit code** in that template so the model can say “if exit code != 0, then …”.
3. **Optional truncation** when output is huge (Aider asks “Add Xk tokens?”); we could truncate and add “(output truncated, N lines)” in the template.

## 3. How to Interact with the Model “Correctly”

From both Aider and our design:

1. **Layered context**: System (rules) → retrieval (knowledge/memory) → task → conversation + last tool results. Clear separation of “what the model must follow” vs “what just happened”.
2. **Structured feedback for tools**: Use a **template** for tool/shell results (command, exit code, stdout, stderr) so the model gets a consistent “observation” format and can plan the next action or exit.
3. **Multiple ways to express “run this”**: Support JSON tool_calls, XML, code blocks, and natural language (“I’ll run: …”) so different models and prompts still lead to execution.
4. **Loop and stagnation controls**: Hash-based loop detection, max tool calls, max consecutive errors, and an explicit exit token so the loop can stop without relying on the model “just saying nothing”.
5. **Role alternation**: After injecting a tool result (as user message), we continue; no need for a synthetic “Ok.” if the protocol expects one more model turn. If the API requires strict user/assistant alternation, a short synthetic assistant message can be used like Aider.

## 4. Summary

- **Aider**: User runs shell via `/run` or `!`; output is formatted with `run_output` and injected as user message; model sees “I ran … And got …” and continues. Edits are parsed from plain text (SEARCH/REPLACE or diff) with fallbacks.
- **Our ReAct**: We parse model output for tool/shell calls, execute them, and inject results. We already have multi-format parsing and loop/stagnation controls.
- **Takeaways**: (1) Use a **structured, template-style format** for tool/shell results (command, exit code, stdout, stderr). (2) Keep **multiple extraction strategies** for commands. (3) Keep **explicit loop and exit semantics** so the agent stops in a predictable way.
