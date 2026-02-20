use anyhow::Result;
use axum::Router;

pub(crate) async fn spawn_test_server<S>(
    app: Router,
    state: S,
    permission_denied_message: &str,
) -> Result<Option<(String, S, tokio::task::JoinHandle<()>)>>
where
    S: Send + 'static,
{
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("{permission_denied_message}");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };

    let addr = listener.local_addr()?;
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    wait_for_listener(addr).await;

    Ok(Some((format!("http://{addr}"), state, handle)))
}

async fn wait_for_listener(addr: std::net::SocketAddr) {
    for _ in 0..20 {
        if tokio::net::TcpStream::connect(addr).await.is_ok() {
            return;
        }
        tokio::time::sleep(std::time::Duration::from_millis(5)).await;
    }
}
