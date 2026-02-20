#![allow(missing_docs)]

use omni_agent::test_support::{
    ManagedControlCommand, ManagedSlashCommand, OutputFormat, ResumeContextCommand,
    SessionAdminAction, SessionFeedbackDirection, SessionInjectionAction, SessionPartitionMode,
    detect_managed_control_command, detect_managed_slash_command, parse_help_command,
    parse_job_status_command, parse_resume_context_command, parse_session_admin_command,
    parse_session_feedback_command, parse_session_injection_command,
    parse_session_partition_command,
};

#[test]
fn test_support_parses_help_and_job_status_output_formats() {
    assert_eq!(parse_help_command("/help"), Some(OutputFormat::Dashboard));
    assert_eq!(parse_help_command("/help json"), Some(OutputFormat::Json));

    let job = parse_job_status_command("/job abc123 json").expect("expected /job json parse");
    assert_eq!(job.job_id, "abc123");
    assert_eq!(job.format, OutputFormat::Json);
}

#[test]
fn test_support_maps_resume_feedback_and_partition_modes() {
    assert_eq!(
        parse_resume_context_command("/resume drop"),
        Some(ResumeContextCommand::Drop)
    );

    let feedback =
        parse_session_feedback_command("/feedback up").expect("expected /feedback up parse");
    assert_eq!(feedback.direction, SessionFeedbackDirection::Up);
    assert_eq!(feedback.format, OutputFormat::Dashboard);

    let partition = parse_session_partition_command("/session partition chat_user json")
        .expect("expected /session partition chat_user json parse");
    assert_eq!(partition.mode, Some(SessionPartitionMode::ChatUser));
    assert_eq!(partition.format, OutputFormat::Json);
    assert_eq!(
        SessionPartitionMode::ChatThreadUser.as_str(),
        "chat_thread_user"
    );

    let injection = parse_session_injection_command("/session inject status json")
        .expect("expected /session inject status json parse");
    assert_eq!(injection.action, SessionInjectionAction::Status);
    assert_eq!(injection.format, OutputFormat::Json);

    let admin =
        parse_session_admin_command("/session admin add 1001,1002").expect("expected admin parse");
    assert_eq!(
        admin.action,
        SessionAdminAction::Add(vec!["1001".to_string(), "1002".to_string()])
    );
}

#[test]
fn test_support_managed_detectors_remain_stable() {
    assert_eq!(
        detect_managed_slash_command("/jobs"),
        Some(ManagedSlashCommand::JobsSummary)
    );
    assert_eq!(
        detect_managed_control_command("/reset"),
        Some(ManagedControlCommand::Reset)
    );
    assert_eq!(
        detect_managed_control_command("/session admin add 1001"),
        Some(ManagedControlCommand::SessionAdmin)
    );
}
