//! Tests for async_io module - asynchronous file operations.

use tokio::io::AsyncWriteExt;

use omni_io::read_text_safe_async;

#[tokio::test]
async fn test_async_read() {
    let dir = tempfile::TempDir::new().unwrap();
    let p = dir.path().join("async.txt");
    tokio::fs::write(&p, "Async Read").await.unwrap();
    assert_eq!(read_text_safe_async(&p, 1024).await.unwrap(), "Async Read");
}

#[tokio::test]
async fn test_async_binary() {
    let dir = tempfile::TempDir::new().unwrap();
    let p = dir.path().join("async_binary.bin");
    let mut file = tokio::fs::File::create(&p).await.unwrap();
    file.write_all(b"\x00\x01\x02\x03").await.unwrap();
    assert!(matches!(
        read_text_safe_async(&p, 1024).await,
        Err(omni_io::IoError::BinaryFile)
    ));
}
