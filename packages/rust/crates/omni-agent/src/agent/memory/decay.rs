pub(in crate::agent) fn should_apply_decay(
    decay_enabled: bool,
    decay_every_turns: usize,
    turn_index: u64,
) -> bool {
    if !decay_enabled {
        return false;
    }
    let every = decay_every_turns.max(1) as u64;
    turn_index > 0 && turn_index % every == 0
}

pub(in crate::agent) fn sanitize_decay_factor(raw: f32) -> f32 {
    if !raw.is_finite() {
        return 0.985;
    }
    raw.clamp(0.5, 0.9999)
}

#[cfg(test)]
#[path = "../../../tests/agent/memory/decay.rs"]
mod tests;
