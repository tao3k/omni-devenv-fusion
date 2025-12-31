# Module 02: The Mechanics of Engineering

> **"Technical writing is engineering. It requires precision, economy, and structure."** — *Barry J. Rosenberg*

This module treats text like code. We apply "refactoring" to sentences to maximize signal-to-noise ratio.

## 1. The Refactoring Table (De-cluttering)

Just as you delete dead code, you must delete dead words. Use this lookup table to refactor your writing:

| The Clutter (Avoid) | The Clean Code (Use) | Why? |
| :--- | :--- | :--- |
| **Utilize** | **Use** | "Utilize" is marketing fluff. "Use" is engineering. |
| **Facilitate** | **Help** | Vague corporate jargon. |
| **In order to** | **To** | Waste of bytes. |
| **At this point in time** | **Now** | "Now" is immediate and powerful. |
| **Is capable of** | **Can** | Avoid converting verbs into nouns. |
| **Perform a calculation** | **Calculate** | Don't "perform" actions; just do them. |
| **Basically / Essentially** | **[Delete]** | Filler words that add zero information. |

## 2. Strong Verbs & Active Voice

### 2.1 The "To Be" Ban
Avoid static verbs like `is`, `are`, `was`, `were` where possible. They describe state, not action.
* *Weak*: "There is a function that handles the request."
* *Strong*: "The function **handles** the request."

### 2.2 Active Voice (Default)
Passive voice hides the "actor" (the subject performing the action).
* *Passive*: "The configuration was loaded." (By whom? The kernel? The app? The user?)
* *Active*: "The application **loaded** the configuration."

## 3. The Law of Parallelism

In lists and bullet points, consistency is mandatory. This is known as **Parallelism**.
* **The Rule**: All items in a list must start with the same part of speech (usually an Imperative Verb for instructions).

> **Bad (Syntax Error)**:
> 1. Open the terminal. (Verb)
> 2. Configuration of the environment. (Noun)
> 3. You should run the build. (Sentence)

> **Good (Parallel)**:
> 1. **Open** the terminal.
> 2. **Configure** the environment.
> 3. **Run** the build.

## 4. Sentence Logic

### 4.1 One Idea Per Sentence
Do not create "run-on" sentences that glue multiple thoughts together with "and".
* *Spaghetti*: "The script downloads the dependencies and then checks for updates and finally compiles the binary."
* *Clean*: "The script downloads dependencies. Then, it checks for updates. Finally, it compiles the binary."

### 4.2 Specificity
* *Ambiguous*: "The system failed."
* *Specific*: "The Nginx process exited with code 1."
