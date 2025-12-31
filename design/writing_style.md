# Engineering Documentation Style Guide

> **Purpose**: This guide codifies the writing standards for the `omni-devenv-fusion` project. It combines principles from William Zinsser's *"On Writing Well"* and Barry Rosenberg's *"Spring Into Technical Writing"* to ensure clarity, brevity, and structure.

---

## 1. Core Principles (The "Laws")

### From *"On Writing Well"* (Simplicity & Humanity)
* **Strip the Clutter**: Every word that serves no function, every long word that could be a short word, every adverb that carries the same meaning that's already in the verb, must go.
    * *Bad*: "At this point in time, we are experiencing a failure."
    * *Good*: "The system failed."
* **Active Voice**: Use active verbs. Passive verbs weaken the impact and hide the actor.
    * *Bad*: "The server was restarted by the script."
    * *Good*: "The script restarted the server."
* **Be specific**: Don't use "implementation" when you mean "script". Don't use "interface" when you mean "CLI".

### From *"Spring Into Technical Writing"* (Structure & Audience)
* **BLUF (Bottom Line Up Front)**: Put the most important information (the conclusion, the fix, the risk) at the very beginning. Engineers are busy; don't bury the lead.
* **Audience Awareness**: Write for the SRE who wakes up at 3 AM to fix this, not for the Professor who grades a thesis.
* **Visual Structure**: Use lists, bold text, and tables to break up walls of text. If a paragraph has more than 5 sentences, split it.

---

## 2. Rules for AI Agents (Orchestrator & Coder)

When generating documentation, commit messages, or design specs, all MCP Personas must adhere to these rules:

### A. Commit Messages (Conventional Commits)
* **Subject Line**: Imperative mood, max 50 chars. (e.g., "Add feature", not "Added feature").
* **Body**: Explain *what* and *why*, not *how* (the code shows how).
* **Reference**: Link to issues or backlog items if they exist.

### B. Technical Explanations (The "What-Why-How" Pattern)
When explaining a complex change (e.g., in a Pull Request or Design Doc), use this strict structure:
1.  **Context (The Problem)**: "The build currently fails on macOS because..."
2.  **Solution (The Fix)**: "We switched from `openssl` to `libressl` in `devenv.nix`."
3.  **Verification (The Proof)**: "Verified by running `just build` on Darwin and Linux."

### C. Tone & Voice
* **Authoritative**: Avoid "I think", "maybe", "it seems". If you are unsure, verify it first.
* **Objective**: Avoid "unfortunately", "happily", "interestingly". Just state the facts.
* **Precise**: Do not use vague words like "various", "some", "a few". Be specific or list them.

---

## 3. Formatting Standards

| Element | Rule | Example |
| :--- | :--- | :--- |
| **Lists** | Use bullet points for non-sequential items. | `* Item A` |
| **Steps** | Use numbered lists for sequential actions. | `1. Run X, 2. Check Y` |
| **Code** | Always wrap commands/variables in backticks. | "Run `just validate`..." |
| **Links** | Use descriptive link text. | `[Nix Manual](...)`, not `[here](...)` |

---

## 4. Checklist for Review (Self-Correction)

Before finalizing any text, ask:
1.  [ ] Can I remove any words without losing meaning?
2.  [ ] Is the most important point in the first sentence?
3.  [ ] Did I use active verbs?
4.  [ ] Is the formatting scanning-friendly (bullet points, bolding)?

> *"Writing is thinking on paper."* — William Zinsser
