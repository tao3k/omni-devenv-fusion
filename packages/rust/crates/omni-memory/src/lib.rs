//! omni-memory - Self-evolving memory engine with Q-Learning and Two-Phase Search.
//!
//! Provides high-performance memory management for AI agents:
//! - Episode storage with vector similarity search
//! - Q-Learning for utility-based episode selection
//! - Two-phase search (semantic recall + Q-value reranking)
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    Python Layer (Orchestration)             │
//! │  - Workflow orchestration                                 │
//! │  - State management                                      │
//! │  - LLM interaction                                       │
//! └─────────────────────────────────────────────────────────────┘
//!                             │
//!                             ▼
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    Rust Layer (Performance Core)           │
//! │  - Episode Store (LanceDB)                                │
//! │  - Q-Table (Q-Learning)                                   │
//! │  - Two-Phase Search                                       │
//! │  - Intent Encoding                                        │
//! └─────────────────────────────────────────────────────────────┘
//! ```
//!
//! # Namespace
//!
//! ```rust
//! use omni_memory::{Episode, QTable, EpisodeStore, TwoPhaseSearch};
//! ```
//!
//! # Examples
//!
//! ```rust
//! use omni_memory::{Episode, EpisodeStore, StoreConfig};
//!
//! let config = StoreConfig {
//!     path: "memory".to_string(),
//!     embedding_dim: 384,
//!     table_name: "episodes".to_string(),
//! };
//! let store = EpisodeStore::new(config);
//! ```
//!
//! ```rust
//! use omni_memory::{QTable, calculate_score};
//!
//! let q_table = QTable::new();
//! q_table.update("ep-001", 1.0);  // Update with reward
//! let q_value = q_table.get_q("ep-001");
//! ```

// ============================================================================
// Core modules
// ============================================================================

mod encoder;
mod episode;
mod gate;
mod persistence;
mod q_table;
mod schema;
mod state_backend;
mod store;
mod two_phase;

// ============================================================================
// Python bindings (optional)
// ============================================================================

#[cfg(feature = "pybindings")]
mod pymodule_impl;

// ============================================================================
// Public exports
// ============================================================================

pub use encoder::IntentEncoder;
pub use episode::Episode;
pub use gate::{
    MemoryGateDecision, MemoryGateEvent, MemoryGatePolicy, MemoryGateVerdict, MemoryLifecycleState,
    MemoryUtilityLedger,
};
pub use q_table::QTable;
pub use schema::EpisodeMetadata;
#[cfg(feature = "valkey")]
pub use state_backend::ValkeyMemoryStateStore;
pub use state_backend::{LocalMemoryStateStore, MemoryStateStore, default_valkey_state_key};
pub use store::{EpisodeStore, MemoryStateSnapshot, StoreConfig};
pub use two_phase::{TwoPhaseConfig, TwoPhaseSearch, calculate_score};

// Python bindings re-exports
#[cfg(feature = "pybindings")]
pub use pymodule_impl::{
    PyEpisode, PyEpisodeStore, PyIntentEncoder, PyQTable, PyStoreConfig, PyTwoPhaseConfig,
    PyTwoPhaseSearch, calculate_score as py_calculate_score, create_episode, create_episode_store,
    create_episode_with_embedding, create_intent_encoder, create_q_table, create_two_phase_search,
    register_memory_module,
};
