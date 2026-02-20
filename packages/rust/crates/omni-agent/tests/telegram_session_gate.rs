#![allow(missing_docs)]

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use omni_agent::SessionGate;
use tokio::sync::oneshot;

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn same_session_is_serialized() {
    let gate = SessionGate::default();
    let first_guard = gate
        .acquire("telegram:-100:888")
        .await
        .expect("first session lock should succeed");

    let gate_for_second = gate.clone();
    let (entered_tx, entered_rx) = oneshot::channel::<()>();
    let blocked = Arc::new(AtomicBool::new(false));
    let blocked_for_task = Arc::clone(&blocked);

    let second = tokio::spawn(async move {
        blocked_for_task.store(true, Ordering::SeqCst);
        let _second_guard = gate_for_second
            .acquire("telegram:-100:888")
            .await
            .expect("second session lock should succeed");
        let _ = entered_tx.send(());
    });

    tokio::time::sleep(Duration::from_millis(50)).await;
    assert!(
        blocked.load(Ordering::SeqCst),
        "second task should be waiting on the same session lock"
    );
    assert!(
        tokio::time::timeout(Duration::from_millis(50), entered_rx)
            .await
            .is_err(),
        "second task should not enter before first lock is dropped"
    );

    drop(first_guard);
    second.await.expect("second task should finish");
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn different_sessions_can_run_in_parallel() {
    let gate = SessionGate::default();
    let first_guard = gate
        .acquire("telegram:-100:888")
        .await
        .expect("first session lock should succeed");

    let gate_for_other = gate.clone();
    let (entered_tx, entered_rx) = oneshot::channel::<()>();
    tokio::spawn(async move {
        let _other_guard = gate_for_other
            .acquire("telegram:-101:888")
            .await
            .expect("other session lock should succeed");
        let _ = entered_tx.send(());
    });

    let _ = tokio::time::timeout(Duration::from_millis(200), entered_rx)
        .await
        .expect("other session should not be blocked");

    drop(first_guard);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn session_entry_is_cleaned_after_last_guard_drops() {
    let gate = SessionGate::default();
    assert_eq!(gate.active_sessions(), 0);
    {
        let _guard = gate
            .acquire("telegram:-100:888")
            .await
            .expect("session lock should succeed");
        assert_eq!(gate.active_sessions(), 1);
    }
    assert_eq!(gate.active_sessions(), 0);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn waiting_tasks_keep_session_entry_alive() {
    let gate = SessionGate::default();
    let first_guard = gate
        .acquire("telegram:-100:888")
        .await
        .expect("first session lock should succeed");

    let gate_for_second = gate.clone();
    let (entered_second_tx, entered_second_rx) = oneshot::channel::<()>();
    let (release_second_tx, release_second_rx) = oneshot::channel::<()>();
    let second = tokio::spawn(async move {
        let _second_guard = gate_for_second
            .acquire("telegram:-100:888")
            .await
            .expect("second session lock should succeed");
        let _ = entered_second_tx.send(());
        let _ = release_second_rx.await;
    });

    tokio::time::sleep(Duration::from_millis(40)).await;
    assert_eq!(
        gate.active_sessions(),
        1,
        "entry should stay tracked while same-session task is waiting"
    );

    drop(first_guard);
    let _ = tokio::time::timeout(Duration::from_millis(200), entered_second_rx)
        .await
        .expect("second task should enter after first guard drops");

    let gate_for_third = gate.clone();
    let (entered_third_tx, entered_third_rx) = oneshot::channel::<()>();
    let third = tokio::spawn(async move {
        let _third_guard = gate_for_third
            .acquire("telegram:-100:888")
            .await
            .expect("third session lock should succeed");
        let _ = entered_third_tx.send(());
    });

    assert!(
        tokio::time::timeout(Duration::from_millis(60), entered_third_rx)
            .await
            .is_err(),
        "third task should still wait while second guard is held"
    );

    let _ = release_second_tx.send(());
    second.await.expect("second task should finish");
    third.await.expect("third task should finish");
    assert_eq!(gate.active_sessions(), 0);
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server"]
async fn distributed_same_session_is_serialized_across_gate_instances() -> anyhow::Result<()> {
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live session gate test");
        return Ok(());
    };
    let prefix = format!(
        "omni-agent:test:session-gate:same-session:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );
    let gate_a =
        SessionGate::new_with_valkey_for_test(valkey_url.clone(), prefix.clone(), 30, Some(5))?;
    let gate_b = SessionGate::new_with_valkey_for_test(valkey_url, prefix, 30, Some(5))?;

    let first_guard = gate_a.acquire("telegram:-100:888").await?;
    let (entered_tx, entered_rx) = oneshot::channel::<()>();
    let second = tokio::spawn(async move {
        let _second_guard = gate_b
            .acquire("telegram:-100:888")
            .await
            .expect("distributed lock should eventually succeed");
        let _ = entered_tx.send(());
    });

    assert!(
        tokio::time::timeout(Duration::from_millis(200), entered_rx)
            .await
            .is_err(),
        "same session across gate instances should be serialized by distributed lease lock"
    );

    drop(first_guard);
    second.await.expect("second task should finish");
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server"]
async fn distributed_different_sessions_run_in_parallel_across_gate_instances() -> anyhow::Result<()>
{
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live session gate test");
        return Ok(());
    };
    let prefix = format!(
        "omni-agent:test:session-gate:parallel-session:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );
    let gate_a =
        SessionGate::new_with_valkey_for_test(valkey_url.clone(), prefix.clone(), 30, Some(5))?;
    let gate_b = SessionGate::new_with_valkey_for_test(valkey_url, prefix, 30, Some(5))?;

    let _first_guard = gate_a.acquire("telegram:-100:888").await?;
    let (entered_tx, entered_rx) = oneshot::channel::<()>();
    tokio::spawn(async move {
        let _second_guard = gate_b
            .acquire("telegram:-101:888")
            .await
            .expect("different sessions should not block each other");
        let _ = entered_tx.send(());
    });

    let _ = tokio::time::timeout(Duration::from_millis(300), entered_rx)
        .await
        .expect("different sessions across gate instances should execute in parallel");
    Ok(())
}
