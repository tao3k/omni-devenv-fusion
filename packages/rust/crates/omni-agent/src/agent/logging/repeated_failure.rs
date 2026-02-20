const REPEATED_FAILURE_LOG_EVERY: u32 = 20;

/// Sample repeated failure logs to avoid pathological spam while preserving
/// first-failure and periodic visibility for operators.
pub(crate) fn should_surface_repeated_failure(failure_streak: u32) -> bool {
    matches!(failure_streak, 1 | 2 | 4 | 8 | 16)
        || failure_streak.is_multiple_of(REPEATED_FAILURE_LOG_EVERY)
}
