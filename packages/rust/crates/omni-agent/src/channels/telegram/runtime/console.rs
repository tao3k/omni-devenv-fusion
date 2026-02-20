use crate::channels::telegram::runtime_config::TelegramRuntimeConfig;

pub(super) fn print_foreground_config(
    runtime_config: &TelegramRuntimeConfig,
    session_gate_backend: &str,
) {
    println!(
        "Foreground config: inbound_queue={} queue={} in_flight={} timeout={}s",
        runtime_config.inbound_queue_capacity,
        runtime_config.foreground_queue_capacity,
        runtime_config.foreground_max_in_flight_messages,
        runtime_config.foreground_turn_timeout_secs
    );
    println!("Session gate backend: {}", session_gate_backend);
}

pub(super) fn print_managed_commands_help() {
    println!("Help command: /help [json]");
    println!("Background commands: /bg <prompt>, /job <id> [json], /jobs [json]");
    println!(
        "Session commands: /session [json], /session budget [json], /session memory [json], /session feedback up|down [json], /session admin [list|set|add|remove|clear] [json], /session partition [mode|on|off] [json], /feedback up|down [json], /reset, /clear, /resume, /resume drop"
    );
}
