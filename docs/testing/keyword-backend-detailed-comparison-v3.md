# Keyword Backend Detailed Comparison (V3 Skill-Based)

- Generated date: 2026-02-11
- Offline snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v3_skill_based.snap`
- Live LLM duel report: `/tmp/keyword-llm-eval-v3-r3.json`
- Top-K: `5`
- Scenario count: `8`

## 1) Offline Aggregate Metrics

| Backend   |    P@5 |    R@5 |    MRR | nDCG@5 | Success@1 |
| --------- | -----: | -----: | -----: | -----: | --------: |
| Tantivy   | 0.2500 | 0.6875 | 1.0000 | 0.9045 |    1.0000 |
| Lance FTS | 0.2250 | 0.6458 | 1.0000 | 0.8717 |    1.0000 |

Primary read:

- Tantivy leads on `P@5` and `R@5` in this skill-based complex suite.
- Both are equal on `MRR` and `Success@1` (all query top1 are relevant).
- Tantivy also leads on `nDCG@5` in V3.

## 2) Per-Scenario Offline Comparison

| Scenario                    | Query                                   | Tantivy (top1 / matched relevant)                                                               | Lance FTS (top1 / matched relevant)                                                  | Offline verdict                    |
| --------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ---------------------------------- |
| repo_refactor_dry_run       | 批量替换 代码 dry run regex refactor    | `advanced_tools.batch_replace` / [`advanced_tools.batch_replace`,`advanced_tools.smart_search`] | `advanced_tools.batch_replace` / [`advanced_tools.batch_replace`]                    | Tantivy better recall/diversity    |
| find_external_crate_symbols | 升级依赖后 查 crate symbol api          | `knowledge.dependency_search` / [`knowledge.dependency_search`]                                 | `knowledge.dependency_search` / [`knowledge.dependency_search`]                      | Tie                                |
| safe_commit_pipeline        | 安全提交 需要扫描并审批 commit workflow | `git.smart_commit` / [`git.smart_commit`]                                                       | `git.smart_commit` / [`git.smart_commit`]                                            | Tie                                |
| crawl_docs_then_summarize   | crawl url 提取 markdown chunk 文档      | `crawl4ai.crawl_url` / [`crawl4ai.crawl_url`]                                                   | `crawl4ai.crawl_url` / [`crawl4ai.crawl_url`]                                        | Tie                                |
| choose_right_tooling        | 先发现能力再执行命令 tool discover      | `skill.discover` / [`skill.discover`]                                                           | `skill.discover` / [`skill.discover`]                                                | Tie                                |
| doc_quality_audit           | 文档润色 markdown 结构 style lint       | `writer.polish_text` / [`writer.polish_text`]                                                   | `writer.polish_text` / [`writer.polish_text`]                                        | Tie                                |
| memory_and_knowledge_lookup | 找历史经验 zk 笔记 hybrid search        | `knowledge.zk_hybrid_search` / [`knowledge.zk_hybrid_search`,`memory.search_memory`]            | `knowledge.zk_hybrid_search` / [`knowledge.zk_hybrid_search`,`memory.search_memory`] | Tie (Tantivy nDCG slightly higher) |
| deep_repo_analysis          | 大型仓库 深度分析 architecture shard    | `researcher.git_repo_analyer` / [`researcher.git_repo_analyer`]                                 | `researcher.git_repo_analyer` / [`researcher.git_repo_analyer`]                      | Tie                                |

## 3) Live LLM Duel Results

Summary:

- Tantivy wins: `0`
- Lance FTS wins: `0`
- Ties: `8`
- Reliable samples: `0/8`
- High-confidence samples: `0/8`
- Avg vote agreement: `0.8333`

Critical reliability note:

- `parse_status` is still predominantly `coerced_non_json`.
- Even with multi-round voting, confidence remained below reliability threshold in all 8 samples.
- Therefore this live duel currently reflects model preference noise, not strong evidence for backend replacement.

Observed alignment:

- Offline metrics favor Tantivy.
- Live duel no longer shows Lance bias (all ties), but reliability is still low.
- Given reliability is weak, offline IR metrics remain the primary decision signal.

## 4) Decision (Current)

Recommended policy:

1. Keep `Tantivy` as default backend for router/tool discovery.
2. Keep `Lance FTS` enabled as optional backend for Lance-native unified data-plane workflows.
3. Re-evaluate after hardening LLM judge protocol.

## 5) Next Hardening Actions

1. Move judge to tool/function-call constrained output (provider-native JSON schema mode) to remove parse ambiguity.
2. Keep majority voting but add backend-A/B randomization to reduce position bias.
3. Persist full raw LLM outputs per query to artifact directory for audit and reproducibility.
