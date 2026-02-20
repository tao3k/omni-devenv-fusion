#!/usr/bin/env bash
set -euo pipefail

echo "contract freeze gate (schemas + canonical snapshots)"

python3 scripts/contract_freeze_lock.py --verify

cargo test -p omni-agent --test contracts -q
cargo test -p xiuxian-qianhuan --test contracts -q

uv run pytest \
  packages/python/foundation/tests/unit/services/test_runtime_contract_schemas.py \
  packages/python/foundation/tests/unit/api/test_skills_monitor_signals_schema.py \
  packages/python/foundation/tests/unit/api/test_link_graph_schema.py \
  packages/python/foundation/tests/unit/api/test_link_graph_policy_schema.py \
  packages/python/foundation/tests/unit/api/test_link_graph_search_options_schema.py \
  packages/python/foundation/tests/unit/api/test_link_graph_checkpoint_schema.py \
  packages/python/foundation/tests/unit/services/test_vector_schema.py::test_vector_payload_snapshot_validates_against_search_schema \
  packages/python/foundation/tests/unit/services/test_vector_schema.py::test_hybrid_payload_snapshot_validates_against_hybrid_schema \
  packages/python/foundation/tests/unit/services/test_vector_schema.py::test_tool_search_payload_snapshot_validates_against_tool_search_schema \
  packages/python/foundation/tests/unit/services/test_contract_consistency.py::test_route_test_canonical_snapshot_validates_against_schema \
  packages/python/foundation/tests/unit/services/test_contract_consistency.py::test_route_test_snapshot_matches_factory_output \
  packages/python/foundation/tests/unit/services/test_contract_consistency.py::test_db_search_vector_snapshot_matches_factory_output \
  packages/python/foundation/tests/unit/services/test_contract_consistency.py::test_db_search_hybrid_snapshot_matches_factory_output \
  -q
