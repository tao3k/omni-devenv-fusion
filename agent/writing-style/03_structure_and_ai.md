# Module 03: Structure for Humans & AI

> **"Context is king. Structure is the castle."** — *Claude Best Practices*

We write for two audiences:
1.  **Humans**: Who scan visually in an "F-Pattern".
2.  **LLMs**: Who rely on semantic hierarchy and explicit examples to understand context.

## 1. Markdown Hierarchy (Semantic Tree)

LLMs parse documents as a DOM tree. Broken hierarchy confuses the model's understanding of relationships.

* **H1 (`#`)**: Document Title (Only one per file).
* **H2 (`##`)**: Major Sections.
* **H3 (`###`)**: Subsections.
* **Rule**: Never skip a level (e.g., jumping from H2 to H4) just for visual styling. It breaks the semantic tree.

## 2. Few-Shot Prompting Principle (Show, Don't Tell)

When documenting commands, APIs, or logic, text descriptions are insufficient for LLMs (and humans). You must provide "Few-Shot Examples."

* **The Pattern**: `Context` $\rightarrow$ `Input` $\rightarrow$ `Expected Output`.

> **Bad (Text Only)**:
> "The `add` command adds a dependency to the project."

> **Good (Few-Shot)**:
> To add a dependency, use the `add` command.
>
> ```bash
> # Command
> omni add requests
>
> # Output
> ✅ Package 'requests' added to pyproject.toml
> 🔒 Lockfile updated
> ```

**Why this matters**: When an LLM reads this, it learns exactly how to simulate the tool's behavior, reducing hallucinations.

## 3. Explicit Context

LLMs (and tired developers) lose track of implicit references.

* **Avoid Floating Pronouns**: Avoid using "It", "They", or "This" if the subject is not in the immediately preceding sentence.
    * *Ambiguous*: "The server calls the client. It then waits." (Who waits?)
    * *Explicit*: "The server calls the client. The server then waits."
* **Location Awareness**: Always specify *where* a command should be run.
    * *Vague*: "Run `make install`."
    * *Explicit*: "Run `make install` from the **project root** directory."

## 4. Visual Scanning (The F-Pattern)

Humans do not read; they scan. Structure your content to support scanning.

* **Front-Load Key Info**: Put the most important keywords at the start of the header or sentence.
    * *Weak*: "If you want to configure the database, the settings are..."
    * *Strong*: "**Database Settings**: Configure them by..."
* **Chunking**: Break text into small paragraphs (3-4 lines max).
* **Callouts**: Use blockquotes or alert blocks for critical warnings.
