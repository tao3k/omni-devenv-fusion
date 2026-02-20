//! Tests for `async_io` module - asynchronous file operations.

use tokio::io::AsyncWriteExt;

use omni_io::read_text_safe_async;

#[tokio::test]
async fn test_async_read() -> Result<(), Box<dyn std::error::Error>> {
    let dir = tempfile::TempDir::new()?;
    let p = dir.path().join("async.txt");
    tokio::fs::write(&p, "Async Read").await?;
    assert_eq!(read_text_safe_async(&p, 1024).await?, "Async Read");
    Ok(())
}

#[tokio::test]
async fn test_async_binary() -> Result<(), Box<dyn std::error::Error>> {
    let dir = tempfile::TempDir::new()?;
    let p = dir.path().join("async_binary.bin");
    let mut file = tokio::fs::File::create(&p).await?;
    file.write_all(b"\x00\x01\x02\x03").await?;
    assert!(matches!(
        read_text_safe_async(&p, 1024).await,
        Err(omni_io::IoError::BinaryFile)
    ));
    Ok(())
}
