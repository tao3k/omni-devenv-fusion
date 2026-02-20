#![allow(missing_docs)]

use omni_agent::test_support::{
    ResumeContextCommand, SessionAdminAction, SessionFeedbackDirection, SessionInjectionAction,
    SessionPartitionMode, is_reset_context_command, parse_background_prompt, parse_help_command,
    parse_job_status_command, parse_jobs_summary_command, parse_resume_context_command,
    parse_session_admin_command, parse_session_context_budget_command,
    parse_session_context_memory_command, parse_session_context_status_command,
    parse_session_feedback_command, parse_session_injection_command,
    parse_session_partition_command,
};

#[test]
fn parse_job_status_accepts_slash_and_plain() {
    let plain = parse_job_status_command("/job job-123").expect("expected /job parse");
    assert_eq!(plain.job_id, "job-123");
    assert!(!plain.format.is_json());

    let plain_no_slash = parse_job_status_command("job job-xyz").expect("expected job parse");
    assert_eq!(plain_no_slash.job_id, "job-xyz");
    assert!(!plain_no_slash.format.is_json());

    let json = parse_job_status_command("/job job-xyz json").expect("expected /job json parse");
    assert_eq!(json.job_id, "job-xyz");
    assert!(json.format.is_json());

    let tagged =
        parse_job_status_command("[bbx-123] /job job-777 json").expect("expected tagged /job");
    assert_eq!(tagged.job_id, "job-777");
    assert!(tagged.format.is_json());
}

#[test]
fn parse_job_status_rejects_invalid_shape() {
    assert_eq!(parse_job_status_command("/job"), None);
    assert_eq!(parse_job_status_command("/job a b"), None);
    assert_eq!(parse_job_status_command("/job a json x"), None);
    assert_eq!(parse_job_status_command("/jobs"), None);
}

#[test]
fn parse_jobs_summary_accepts_slash_and_plain() {
    assert!(
        !parse_jobs_summary_command("/jobs")
            .expect("expected /jobs parse")
            .is_json()
    );
    assert!(
        !parse_jobs_summary_command("jobs")
            .expect("expected jobs parse")
            .is_json()
    );
    assert!(
        parse_jobs_summary_command("/jobs json")
            .expect("expected /jobs json parse")
            .is_json()
    );
    assert_eq!(parse_jobs_summary_command("/job x"), None);
    assert_eq!(parse_jobs_summary_command("/jobs pretty"), None);
}

#[test]
fn parse_background_accepts_bg_and_research() {
    assert_eq!(
        parse_background_prompt("/bg crawl https://example.com"),
        Some("crawl https://example.com".to_string())
    );
    assert_eq!(
        parse_background_prompt("research compare rust actors"),
        Some("research compare rust actors".to_string())
    );
    assert_eq!(
        parse_background_prompt("/research compare rust actors"),
        Some("research compare rust actors".to_string())
    );
}

#[test]
fn parse_background_rejects_empty_or_unrelated() {
    assert_eq!(parse_background_prompt("/bg"), None);
    assert_eq!(parse_background_prompt("hello"), None);
}

#[test]
fn parse_session_commands_accepts_aliases() {
    assert!(parse_help_command("/help").is_some());
    assert!(parse_help_command("help").is_some());
    assert!(parse_help_command("/help json").is_some());
    assert!(parse_help_command("/slash help").is_some());
    assert!(parse_help_command("/slash help json").is_some());
    assert!(parse_help_command("/commands").is_some());
    assert!(parse_help_command("/commands json").is_some());
    assert!(parse_session_context_status_command("/session").is_some());
    assert!(parse_session_context_status_command("session status").is_some());
    assert!(parse_session_context_status_command("/window stats").is_some());
    assert!(parse_session_context_status_command("context info").is_some());
    assert!(parse_session_context_budget_command("/session budget").is_some());
    assert!(parse_session_context_budget_command("window budget").is_some());
    assert!(parse_session_context_budget_command("/context budget").is_some());
    assert!(parse_session_context_memory_command("/session memory").is_some());
    assert!(parse_session_context_memory_command("window recall").is_some());
    assert!(parse_session_context_memory_command("/context recall").is_some());
    assert!(
        parse_session_context_status_command("/session json")
            .expect("expected /session json")
            .is_json()
    );
    assert!(
        parse_session_context_status_command("/window status json")
            .expect("expected /window status json")
            .is_json()
    );
    assert!(
        parse_session_context_budget_command("/session budget json")
            .expect("expected /session budget json")
            .is_json()
    );
    assert!(
        !parse_session_context_budget_command("/context budget")
            .expect("expected /context budget")
            .is_json()
    );
    assert!(
        parse_session_context_memory_command("/session memory json")
            .expect("expected /session memory json")
            .is_json()
    );
    assert!(
        parse_session_context_memory_command("/session recall json")
            .expect("expected /session recall json")
            .is_json()
    );
    assert!(
        parse_session_context_memory_command("[bbx-123] /session memory json")
            .expect("expected tagged /session memory json")
            .is_json()
    );
    let feedback_up =
        parse_session_feedback_command("/session feedback up").expect("expected feedback up");
    assert_eq!(feedback_up.direction, SessionFeedbackDirection::Up);
    assert!(!feedback_up.format.is_json());
    let feedback_down_json = parse_session_feedback_command("/feedback down json")
        .expect("expected short feedback down json");
    assert_eq!(feedback_down_json.direction, SessionFeedbackDirection::Down);
    assert!(feedback_down_json.format.is_json());
    let feedback_positive = parse_session_feedback_command("context feedback positive")
        .expect("expected context feedback positive");
    assert_eq!(feedback_positive.direction, SessionFeedbackDirection::Up);
    let feedback_failure = parse_session_feedback_command("[bbx-123] /window feedback failure")
        .expect("expected tagged window feedback failure");
    assert_eq!(feedback_failure.direction, SessionFeedbackDirection::Down);
    let inject_status =
        parse_session_injection_command("/session inject").expect("expected session inject status");
    assert_eq!(inject_status.action, SessionInjectionAction::Status);
    assert!(!inject_status.format.is_json());
    let inject_status_json = parse_session_injection_command("/session inject status json")
        .expect("expected session inject status json");
    assert_eq!(inject_status_json.action, SessionInjectionAction::Status);
    assert!(inject_status_json.format.is_json());
    let inject_clear = parse_session_injection_command("/session inject clear json")
        .expect("expected session inject clear json");
    assert_eq!(inject_clear.action, SessionInjectionAction::Clear);
    assert!(inject_clear.format.is_json());
    let inject_set = parse_session_injection_command("/session inject <qa><q>a</q><a>b</a></qa>")
        .expect("expected session inject payload");
    assert_eq!(
        inject_set.action,
        SessionInjectionAction::SetXml("<qa><q>a</q><a>b</a></qa>".to_string())
    );
    let admin_list = parse_session_admin_command("/session admin").expect("expected admin list");
    assert_eq!(admin_list.action, SessionAdminAction::List);
    assert!(!admin_list.format.is_json());
    let admin_list_json =
        parse_session_admin_command("/session admin json").expect("expected admin list json");
    assert_eq!(admin_list_json.action, SessionAdminAction::List);
    assert!(admin_list_json.format.is_json());
    let admin_set = parse_session_admin_command("/session admin set 1001,1002 json")
        .expect("expected admin set");
    assert_eq!(
        admin_set.action,
        SessionAdminAction::Set(vec!["1001".to_string(), "1002".to_string()])
    );
    assert!(admin_set.format.is_json());
    let admin_add =
        parse_session_admin_command("/window admin add 2001 2002").expect("expected admin add");
    assert_eq!(
        admin_add.action,
        SessionAdminAction::Add(vec!["2001".to_string(), "2002".to_string()])
    );
    let admin_remove =
        parse_session_admin_command("/context admin remove 1001").expect("expected admin remove");
    assert_eq!(
        admin_remove.action,
        SessionAdminAction::Remove(vec!["1001".to_string()])
    );
    let admin_clear =
        parse_session_admin_command("/session admin clear json").expect("expected admin clear");
    assert_eq!(admin_clear.action, SessionAdminAction::Clear);
    assert!(admin_clear.format.is_json());
    let admin_implicit_set = parse_session_admin_command("/session admin 3001,3002")
        .expect("expected implicit admin set");
    assert_eq!(
        admin_implicit_set.action,
        SessionAdminAction::Set(vec!["3001".to_string(), "3002".to_string()])
    );
    let partition_status =
        parse_session_partition_command("/session partition").expect("expected partition status");
    assert!(partition_status.mode.is_none());
    assert!(!partition_status.format.is_json());
    let partition_status_json = parse_session_partition_command("/session partition json")
        .expect("expected partition status json");
    assert!(partition_status_json.mode.is_none());
    assert!(partition_status_json.format.is_json());
    let partition_on =
        parse_session_partition_command("/session partition on").expect("expected partition on");
    assert_eq!(partition_on.mode, Some(SessionPartitionMode::Chat));
    assert_eq!(SessionPartitionMode::Chat.as_str(), "chat");
    let partition_off =
        parse_session_partition_command("/session partition off").expect("expected partition off");
    assert_eq!(partition_off.mode, Some(SessionPartitionMode::ChatUser));
    let partition_explicit =
        parse_session_partition_command("/session partition chat_thread_user json")
            .expect("expected explicit partition json");
    assert_eq!(
        partition_explicit.mode,
        Some(SessionPartitionMode::ChatThreadUser)
    );
    assert!(partition_explicit.format.is_json());
    assert!(is_reset_context_command("/reset"));
    assert!(is_reset_context_command("reset"));
    assert!(is_reset_context_command("/clear"));
    assert!(is_reset_context_command("clear"));
    assert_eq!(
        parse_resume_context_command("/resume"),
        Some(ResumeContextCommand::Restore)
    );
    assert_eq!(
        parse_resume_context_command("/resume status"),
        Some(ResumeContextCommand::Status)
    );
    assert_eq!(
        parse_resume_context_command("/resume stats"),
        Some(ResumeContextCommand::Status)
    );
    assert_eq!(
        parse_resume_context_command("resume info"),
        Some(ResumeContextCommand::Status)
    );
    assert_eq!(
        parse_resume_context_command("/resume drop"),
        Some(ResumeContextCommand::Drop)
    );
    assert_eq!(
        parse_resume_context_command("resume discard"),
        Some(ResumeContextCommand::Drop)
    );
}

#[test]
fn parse_session_commands_rejects_invalid_shape() {
    assert!(parse_help_command("/help pretty").is_none());
    assert!(parse_help_command("/slash help pretty").is_none());
    assert!(parse_help_command("/help json extra").is_none());
    assert!(parse_help_command("/commands pretty").is_none());
    assert!(parse_session_context_status_command("/session now").is_none());
    assert!(parse_session_context_status_command("window maybe").is_none());
    assert!(parse_session_context_budget_command("/session").is_none());
    assert!(parse_session_context_budget_command("/session budgeting").is_none());
    assert!(parse_session_context_memory_command("/session memorying").is_none());
    assert!(parse_session_context_status_command("/session status pretty").is_none());
    assert!(parse_session_context_budget_command("/session budget pretty").is_none());
    assert!(parse_session_context_memory_command("/session memory pretty").is_none());
    assert!(parse_session_context_status_command("/session budget json").is_none());
    assert!(parse_session_context_budget_command("/session json").is_none());
    assert!(parse_session_context_memory_command("/session json").is_none());
    assert!(parse_session_context_memory_command("/session budget json").is_none());
    assert!(parse_session_partition_command("/session partition maybe").is_none());
    assert!(parse_session_partition_command("/session partition chat pretty").is_none());
    assert!(parse_session_partition_command("/session partition json extra").is_none());
    assert!(parse_session_partition_command("/session partition guild_channel_user").is_none());
    assert!(parse_session_partition_command("/session partition channel").is_none());
    assert!(parse_session_partition_command("/session partition guild_user").is_none());
    assert!(parse_session_feedback_command("/session feedback").is_none());
    assert!(parse_session_feedback_command("/session feedback maybe").is_none());
    assert!(parse_session_feedback_command("/feedback").is_none());
    assert!(parse_session_feedback_command("/feedback maybe json").is_none());
    assert!(parse_session_feedback_command("/feedback up extra").is_none());
    assert!(parse_session_feedback_command("/session feedback up pretty").is_none());
    assert!(parse_session_injection_command("/session inject set").is_none());
    assert!(parse_session_injection_command("/session inject clear now").is_none());
    assert!(parse_session_admin_command("/session admin add").is_none());
    assert!(parse_session_admin_command("/session admin clear now").is_none());
    assert!(parse_session_admin_command("/session admin list now").is_none());
    assert!(parse_session_admin_command("/session admin json extra").is_none());
    assert!(!is_reset_context_command("/reset now"));
    assert!(!is_reset_context_command("hello"));
    assert!(parse_resume_context_command("/clear").is_none());
    assert!(parse_resume_context_command("/resume now").is_none());
}
