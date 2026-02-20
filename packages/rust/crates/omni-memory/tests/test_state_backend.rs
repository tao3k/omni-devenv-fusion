#![allow(missing_docs)]

use omni_memory::{StoreConfig, default_valkey_state_key};

fn store_config(path: &str, table_name: &str) -> StoreConfig {
    StoreConfig {
        path: path.to_string(),
        embedding_dim: 384,
        table_name: table_name.to_string(),
    }
}

#[test]
fn default_valkey_state_key_is_deterministic_for_same_store_config() {
    let config = store_config("/tmp/omni-memory", "episodes");

    let key_a = default_valkey_state_key("omni-agent:memory", &config);
    let key_b = default_valkey_state_key("omni-agent:memory", &config);

    assert_eq!(key_a, key_b);
}

#[test]
fn default_valkey_state_key_changes_with_store_identity() {
    let base = store_config("/tmp/omni-memory", "episodes");
    let changed_path = store_config("/tmp/omni-memory-other", "episodes");
    let changed_table = store_config("/tmp/omni-memory", "episodes_v2");

    let base_key = default_valkey_state_key("omni-agent:memory", &base);
    let path_key = default_valkey_state_key("omni-agent:memory", &changed_path);
    let table_key = default_valkey_state_key("omni-agent:memory", &changed_table);

    assert_ne!(base_key, path_key);
    assert_ne!(base_key, table_key);
}
