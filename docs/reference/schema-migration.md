# Schema Migration (omni-vector)

> One-click migrate command and roadmap: schema-only vs full table rewrite.

See also: [Vector Router Schema Contract](vector-router-schema-contract.md), [Vector Search Options Contract](vector-search-options-contract.md).

---

## 1. Current behaviour

- **CLI**: `omni db migrate DATABASE [--table TABLE] [--force] [--strategy STRATEGY] [--json]`
  - Default: dry-run (list pending migrations).
  - `--force`: apply all pending migrations.
  - `--strategy rewrite`: full table rewrite with **bounded memory** (stream scan → convert per batch → drop table → create with first batch → append remaining batches one at a time). Default and only supported value for now.
- **Version history** (in Rust: `OMNI_SCHEMA_VERSION = 2`):
  - **v1**: TOOL_NAME `Utf8`
  - **v2**: TOOL_NAME `Dictionary(Int32, Utf8)`; SKILL_NAME/CATEGORY already Dictionary; **routing_keywords** and **intents** are `List<Utf8>` (new tables). Read path supports legacy Utf8 (space/pipe-separated) and List.
  - **v3** (planned): e.g. `metadata` as `Struct`

Current implementation is **streaming rewrite**: scan batch-by-batch, convert each batch, drop table, create with first batch, then append remaining batches one at a time so memory stays bounded. Safe and correct; cost is I/O and time on large tables.

### P1 finding: Lance 2.0 and Utf8 → Dictionary

Lance 2.0 `Dataset::alter_columns` supports changing column type via `ColumnAlteration::cast_to(DataType)`, but it only allows casts that satisfy **same-type-family** rules (see `is_upcast_downcast` in Lance’s `schema_evolution.rs`): e.g. integer↔integer, Utf8↔LargeUtf8. **Utf8 → Dictionary is not allowed** (Dictionary is a different family). So v1→v2 (TOOL_NAME Utf8→Dictionary) cannot use the alter path and must use the existing full table rewrite. No change required for P1; the current implementation is the correct approach until Lance adds support for such casts or we introduce a custom alter UDF.

### P2 (done)

- **Bounded memory**: migrate now streams the table (one batch at a time), converts, and appends incrementally instead of loading all batches into memory.
- **CLI**: `omni db migrate DATABASE --strategy rewrite` is implemented (default). `--strategy in-place` is planned when Lance supports it.

---

## 3. Usage examples

```bash
# List pending migrations (dry run)
omni db migrate skills
omni db migrate knowledge --table knowledge_chunks

# Apply migrations (rewrite strategy, bounded memory)
omni db migrate skills --force
omni db migrate skills --force --strategy rewrite

# JSON output
omni db migrate skills --json
omni db migrate skills --force --json
```

---

## 4. Implementation locations

- **Rust**: `packages/rust/crates/omni-vector/src/ops/migration.rs` — `check_migrations`, `migrate`, v1→v2 conversion; version inference in `schema_version_from_schema`.
- **Python**: `omni.foundation.bridge.rust_vector` — `check_migrations`, `migrate`; CLI: `db migrate` in `packages/python/agent/src/omni/agent/cli/commands/db/admin.py`.
