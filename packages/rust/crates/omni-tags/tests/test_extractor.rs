//! Tests for extractor module - code outline extraction.

use std::fs::File;
use std::io::Write;
use tempfile::TempDir;

use omni_tags::TagExtractor;

#[test]
fn test_python_outline() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("test.py");
    let content = r#"
class Agent:
    def __init__(self, name: str):
        pass

    async def run(self, task: str) -> None:
        pass

def helper_function(x: int) -> int:
    return x * 2

class AnotherClass:
    pass
"#;
    File::create(&path)
        .unwrap()
        .write_all(content.as_bytes())
        .unwrap();

    let outline = TagExtractor::outline_file(&path, Some("python")).unwrap();

    assert!(outline.contains("class Agent"));
    assert!(outline.contains("def helper_function"));
}

#[test]
fn test_rust_outline() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("test.rs");
    let content = r#"
pub struct ContextLoader {
    root: PathBuf,
}

impl ContextLoader {
    pub fn new() -> Self {
        Self { root: PathBuf::new() }
    }

    fn load_file(&self, path: &str) -> String {
        String::new()
    }
}

trait Printable {
    fn print(&self);
}
"#;
    File::create(&path)
        .unwrap()
        .write_all(content.as_bytes())
        .unwrap();

    let outline = TagExtractor::outline_file(&path, Some("rust")).unwrap();

    // Check that output contains key Rust elements
    assert!(outline.contains("ContextLoader"));
    assert!(outline.contains("impl"));
    assert!(outline.contains("Printable"));
}
