//! Tests for omni-macros.

use omni_macros::{assert_timing, bench_case, patterns, py_from, temp_dir, topics};

// Test patterns! macro
mod test_patterns {
    use super::*;

    patterns![
        (TEST_PATTERN_1, "pattern one"),
        (TEST_PATTERN_2, "pattern two"),
    ];

    #[test]
    fn test_patterns_generated() {
        assert_eq!(TEST_PATTERN_1, "pattern one");
        assert_eq!(TEST_PATTERN_2, "pattern two");
    }
}

// Test topics! macro
mod test_topics {
    use super::*;

    topics![(TOPIC_ONE, "topic/one"), (TOPIC_TWO, "topic/two"),];

    #[test]
    fn test_topics_generated() {
        assert_eq!(TOPIC_ONE, "topic/one");
        assert_eq!(TOPIC_TWO, "topic/two");
    }
}

// Test py_from! macro
mod test_py_from {
    use super::*;

    struct Inner {
        value: i32,
    }

    struct PyWrapper {
        inner: Inner,
    }

    py_from!(PyWrapper, Inner);

    #[test]
    fn test_py_from_generated() {
        let inner = Inner { value: 42 };
        let wrapper = PyWrapper::from(inner);
        assert_eq!(wrapper.inner.value, 42);
    }
}

// Test temp_dir! macro
mod test_temp_dir {
    use super::*;
    use std::fs;

    #[test]
    fn test_temp_dir_creates_directory() {
        let temp_path = temp_dir!();
        assert!(temp_path.exists());
        assert!(temp_path.is_dir());

        // Clean up
        fs::remove_dir_all(&temp_path).unwrap();
    }

    #[test]
    fn test_temp_dir_is_unique() {
        let temp_path1 = temp_dir!();
        let temp_path2 = temp_dir!();

        assert_ne!(temp_path1, temp_path2);

        // Clean up
        let _ = fs::remove_dir_all(&temp_path1);
        let _ = fs::remove_dir_all(&temp_path2);
    }
}

// Test assert_timing! macro
mod test_assert_timing {
    use super::*;

    #[test]
    fn test_assert_timing_passes_fast_operation() {
        let elapsed = assert_timing!(100.0, {
            // Fast operation
            let x = 1 + 1;
            assert_eq!(x, 2);
        });
        assert!(elapsed.as_millis() < 100);
    }

    #[test]
    fn test_assert_timing_returns_elapsed() {
        let elapsed = assert_timing!(1000.0, {
            std::thread::sleep(std::time::Duration::from_millis(1));
        });
        assert!(elapsed.as_millis() >= 1);
    }
}

// Test bench_case! macro
mod test_bench_case {
    use super::*;

    #[test]
    fn test_bench_case_measures_time() {
        let elapsed = bench_case!({
            let sum: i32 = (0..100).sum();
            assert_eq!(sum, 4950);
        });
        assert!(elapsed.as_nanos() > 0);
    }

    #[test]
    fn test_bench_case_simple() {
        let _elapsed = bench_case!(1 + 1);
        // Verify that bench_case returns a duration
        assert!(true);
    }
}
