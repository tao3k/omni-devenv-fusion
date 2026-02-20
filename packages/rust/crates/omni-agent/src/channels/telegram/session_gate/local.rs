use std::sync::Arc;
use std::sync::atomic::Ordering;

use super::types::SessionPermit;

impl Drop for SessionPermit {
    fn drop(&mut self) {
        let previous = self.entry.permits.fetch_sub(1, Ordering::AcqRel);
        debug_assert!(previous > 0, "session gate permit underflow");
        if previous != 1 {
            return;
        }

        let mut map = self
            .inner
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        let should_remove = map
            .get(&self.session_id)
            .is_some_and(|current| Arc::ptr_eq(current, &self.entry))
            && self.entry.permits.load(Ordering::Acquire) == 0;
        if should_remove {
            map.remove(&self.session_id);
        }
    }
}
