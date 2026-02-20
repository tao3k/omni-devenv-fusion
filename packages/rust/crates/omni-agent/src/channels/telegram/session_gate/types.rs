use std::collections::HashMap;
use std::sync::Arc;
use std::sync::Mutex as StdMutex;
use std::sync::atomic::AtomicUsize;

use tokio::sync::{Mutex, OwnedMutexGuard};

use super::valkey::{DistributedLeaseGuard, ValkeySessionGateBackend};

#[derive(Clone)]
pub struct SessionGate {
    pub(super) inner: Arc<StdMutex<HashMap<String, Arc<SessionGateEntry>>>>,
    pub(super) backend: SessionGateBackend,
}

#[derive(Default)]
pub(super) struct SessionGateEntry {
    pub(super) lock: Arc<Mutex<()>>,
    pub(super) permits: AtomicUsize,
}

pub struct SessionGuard {
    pub(super) _distributed_lease: Option<DistributedLeaseGuard>,
    pub(super) _lock_guard: OwnedMutexGuard<()>,
    pub(super) _permit: SessionPermit,
}

pub(super) struct SessionPermit {
    pub(super) session_id: String,
    pub(super) inner: Arc<StdMutex<HashMap<String, Arc<SessionGateEntry>>>>,
    pub(super) entry: Arc<SessionGateEntry>,
}

#[derive(Clone)]
pub(super) enum SessionGateBackend {
    Memory,
    Valkey(Arc<ValkeySessionGateBackend>),
}
