use super::types::LINK_GRAPH_SALIENCY_SCHEMA_VERSION;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

pub(crate) fn saliency_slot(node_id: &str) -> String {
    let mut hasher = DefaultHasher::new();
    node_id.hash(&mut hasher);
    LINK_GRAPH_SALIENCY_SCHEMA_VERSION.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

pub(crate) fn saliency_key(node_id: &str, key_prefix: &str) -> String {
    format!("{key_prefix}:saliency:{}", saliency_slot(node_id))
}

pub(crate) fn edge_out_key(from_node_id: &str, key_prefix: &str) -> String {
    format!("{key_prefix}:kg:edge:out:{from_node_id}")
}

pub(crate) fn edge_in_key(to_node_id: &str, key_prefix: &str) -> String {
    format!("{key_prefix}:kg:edge:in:{to_node_id}")
}
