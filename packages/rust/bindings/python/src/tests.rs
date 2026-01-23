//! Unit tests for utils module.
//!
//! Tests for panic safety utilities.

#[cfg(test)]
mod test_utils {
    use crate::utils::run_safe;
    use pyo3::PyErr;

    /// Test that normal operations pass through successfully.
    #[test]
    fn test_run_safe_normal() {
        let result: Result<i32, PyErr> = run_safe(|| Ok(42));
        assert_eq!(result.unwrap(), 42);
    }

    /// Test that panics are caught and converted to errors.
    #[test]
    fn test_run_safe_panic() {
        let result: Result<i32, PyErr> = run_safe(|| {
            panic!("Test panic message");
        });
        assert!(result.is_err());
    }

    /// Test that panic with String payload works.
    #[test]
    fn test_run_safe_panic_string() {
        let result: Result<i32, PyErr> = run_safe(|| {
            panic!("String panic");
        });
        assert!(result.is_err());
        let err_msg = result.unwrap_err().to_string();
        assert!(err_msg.contains("Rust panic intercepted"));
    }
}
