# Omni-DevEnv Technical Writing Standard

> **The Grand Unification of Documentation**
>
> This standard unifies the precision of engineering with the clarity of teaching. It is built upon four pillars:
> 1.  **The Feynman Principle**: Clarity through mental models and concrete examples.
> 2.  **The Zinsser Principle**: Humanity, rhythm, and the elimination of clutter.
> 3.  **The Rosenberg Standard**: Engineering rigour, strong verbs, and parallelism.
> 4.  **The Claude Axiom**: Structural optimization for AI context and few-shot reasoning.

## Module Reference

| Module | Focus | Key Questions Answered |
| :--- | :--- | :--- |
| [**01_philosophy.md**](./01_philosophy.md) | **Mindset & Mental Models** | How do I explain complex concepts simply? How do I sound human? |
| [**02_mechanics.md**](./02_mechanics.md) | **Grammar & Precision** | How do I refactor sentences? Which words should I delete? |
| [**03_structure_and_ai.md**](./03_structure_and_ai.md) | **Format & AI Optimization** | How do I structure Markdown for LLMs? How do I prevent hallucinations? |

---

## The Final Commit Checklist (Mental Linter)

Before merging any documentation, run this "linter" on your writing.

### Logic & Teaching (Feynman/Zinsser)
- [ ] **Concrete First**: Did I provide a real-world example or analogy *before* explaining the abstract theory?
- [ ] **ELI5**: Did I explain jargon? Would a smart junior developer understand this without external help?
- [ ] **Human Tone**: Did I read it aloud? Does it sound like a human conversation, or a corporate robot?

### Mechanics & Precision (Rosenberg)
- [ ] **De-clutter**: Did I replace "utilize" with "use", and "in order to" with "to"?
- [ ] **Active Voice**: Did I state *who* is acting? (e.g., "The script builds the app" vs "The app is built").
- [ ] **Parallelism**: Do all list items start with the same part of speech (e.g., all Imperative Verbs)?

### AI & Structure (Claude)
- [ ] **Few-Shot Examples**: Did I provide `Input -> Output` code blocks for every command or function described?
- [ ] **Hierarchy**: Is the Markdown nesting (H1 -> H2 -> H3) logical and unbroken?
- [ ] **Explicit Context**: Did I avoid ambiguous pronouns like "it" or "that" when referring to complex systems?

> "Writing is thinking on paper. If the documentation is unclear, the design is likely unclear."
