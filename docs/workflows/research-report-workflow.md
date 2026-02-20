# Research Report Workflow: From "Give me the UltraRAG report" to Delivery

When you ask for "the UltraRAG research report" or "list the UltraRAG research report", the assistant follows this workflow. **All report discovery goes through LinkGraph** (the notebook indexes `.data/harvested`); the assistant does not check paths or read files by path first.

## Overview

```
You: "Give me the UltraRAG research report"
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ 1. Query LinkGraph only                                                  │
│    knowledge.search("UltraRAG") or search(..., mode="link_graph")       │
│    → If LinkGraph returns notes (e.g. from .data/harvested/.../UltraRAG) │
│      the report exists; use those results to list and summarize.  │
└───────────────────────────────────────────────────────────────────┘
        │
        ├── LinkGraph has hits ──► 2a. Summarize and list from LinkGraph results
        │
        └── LinkGraph has no hits ──► 2b. Generate report (researcher), then LinkGraph will index it
```

---

## 2a. Report exists (LinkGraph found it): summarize and list from LinkGraph results

Do **not** read `.data/harvested/OpenBMB/UltraRAG/` by path. Use the notes LinkGraph returned:

- From **search** (default hybrid) or **search(..., mode="link_graph")** results you get note paths, titles, and content snippets.
- Summarize and list those notes (paths and titles); paste key excerpts from the result content.
- If the user needs the full index or a specific shard, open the **path that LinkGraph returned** for that note (e.g. `.data/harvested/OpenBMB/UltraRAG/index.md`), not by guessing the path up front.

**Delivery:** Present what LinkGraph returned: which notes matched, their paths and titles, and short summaries or quotes. Only open a file by path when that path came from a LinkGraph result.

---

## 2b. Report does not exist (LinkGraph had no hits): generate then rely on LinkGraph

When LinkGraph search for "UltraRAG" (or similar) returns nothing:

| Step   | Action                 | Notes                                                                                                                                                                                                    |
| ------ | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **B1** | **Call researcher**    | `researcher.run_research_graph(repo_url="https://github.com/OpenBMB/UltraRAG", request="...")`.                                                                                                          |
| **B2** | **Wait for workflow**  | Clone → Map → Architect → shards → `index.md`. Return includes `harvest_dir`.                                                                                                                            |
| **B3** | **Immediate delivery** | Use `harvest_dir` from the return to summarize (e.g. read `index.md` **only** from that returned path). After that, future discovery is again via LinkGraph only—no need to remember or re-read by path. |

**Delivery:** Say the report was generated and give a short summary from the run’s `harvest_dir`. Next time the user asks, use LinkGraph search again; the new notes will be in the index.

---

## Recommended assistant steps

1. **Discover via LinkGraph only**
   - Call `knowledge.search("UltraRAG")` or `knowledge.search("UltraRAG research report")` (default hybrid).
   - If there are hits → go to step 2. If none → go to step 3.

2. **If LinkGraph returned hits**
   - Summarize and list the returned notes (paths, titles, snippets). Optionally open a file **only if** its path came from a LinkGraph result (e.g. user asks for the full index).
   - Do not "check if the directory exists" or "read index.md" by constructing the path yourself.

3. **If LinkGraph returned no hits**
   - Call `researcher.run_research_graph(repo_url="https://github.com/OpenBMB/UltraRAG", request="...")`.
   - After it finishes, use the returned `harvest_dir` once to summarize and point to the new report. Later requests: use LinkGraph again.

4. **Optional**
   - For semantic recall over reports, add `.data/harvested` to `knowledge_dirs` and run `omni sync knowledge`. Discovery of _which_ report exists still goes through LinkGraph.

---

## Config and skills

- **Report output path:** `references.yaml` → `link_graph.harvested` = `.data/harvested`; reports live under `.data/harvested/<owner>/<repo_name>/`. LinkGraph indexes them; no need to look at the path unless LinkGraph gave it to you.
- **Generate report:** `researcher.run_research_graph(repo_url, request)`.
- **Retrieve existing report:** **LinkGraph only** — `knowledge.search` (default hybrid) or `knowledge.search(..., mode="link_graph")`. Do not probe the filesystem or read by path to "see if the report exists".

Summary: use LinkGraph to find the report; only then use paths that LinkGraph returned. Do not look at the file or directory by path first.
