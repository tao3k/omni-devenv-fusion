from __future__ import annotations

import importlib.util
from pathlib import Path

from omni.foundation.runtime.gitops import get_project_root


def _load_resolver_module():
    module_path = Path(get_project_root()) / "scripts" / "channel" / "test_config_resolver.py"
    spec = importlib.util.spec_from_file_location("channel_test_config_resolver", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_username_from_settings_prefers_user_override(tmp_path: Path, monkeypatch) -> None:
    resolver = _load_resolver_module()

    system_settings = tmp_path / "packages" / "conf" / "settings.yaml"
    system_settings.parent.mkdir(parents=True)
    system_settings.write_text('telegram:\n  allowed_users: "system_user"\n', encoding="utf-8")

    user_conf_home = tmp_path / "custom_conf"
    user_settings = user_conf_home / "omni-dev-fusion" / "settings.yaml"
    user_settings.parent.mkdir(parents=True)
    user_settings.write_text(
        'telegram:\n  allowed_users: "override_user,backup_user"\n',
        encoding="utf-8",
    )

    monkeypatch.setenv("PRJ_CONFIG_HOME", str(user_conf_home))
    assert resolver.username_from_settings(tmp_path) == "override_user"


def test_username_from_settings_uses_system_when_user_missing(tmp_path: Path, monkeypatch) -> None:
    resolver = _load_resolver_module()

    system_settings = tmp_path / "packages" / "conf" / "settings.yaml"
    system_settings.parent.mkdir(parents=True)
    system_settings.write_text('telegram:\n  allowed_users: "system_user"\n', encoding="utf-8")

    monkeypatch.delenv("PRJ_CONFIG_HOME", raising=False)
    assert resolver.username_from_settings(tmp_path) == "system_user"


def test_username_from_runtime_log_strips_ansi(tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "\x1b[2m2026-02-18T00:00:00Z\x1b[0m INFO --allowed-users tao3k,backup\n",
        encoding="utf-8",
    )

    assert resolver.username_from_runtime_log(log_file) == "tao3k"


def test_session_ids_from_runtime_log_two_part_key(tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=1304799691:1304799691\n",
        encoding="utf-8",
    )

    assert resolver.session_ids_from_runtime_log(log_file) == (1304799691, 1304799691, None)


def test_session_ids_from_runtime_log_three_part_key(tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        "INFO Parsed message, forwarding to agent session_key=-100200300:777:1304799691\n",
        encoding="utf-8",
    )

    assert resolver.session_ids_from_runtime_log(log_file) == (-100200300, 1304799691, 777)


def test_group_profile_value_reads_profile_env_file(tmp_path: Path, monkeypatch) -> None:
    resolver = _load_resolver_module()

    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text(
        "OMNI_TEST_CHAT_ID=-5101776367\n"
        "OMNI_TEST_CHAT_B=-5020317863\n"
        "OMNI_TEST_CHAT_C=-5292802281\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.delenv("OMNI_TEST_CHAT_ID", raising=False)

    assert resolver.group_profile_value("OMNI_TEST_CHAT_ID", tmp_path) == "-5101776367"
    assert resolver.group_profile_int("OMNI_TEST_CHAT_ID", tmp_path) == -5101776367
    assert resolver.group_profile_chat_ids(tmp_path) == (
        -5101776367,
        -5020317863,
        -5292802281,
    )


def test_group_profile_value_prefers_process_env(monkeypatch, tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    profile = tmp_path / "agent-channel-groups.env"
    profile.write_text("OMNI_TEST_CHAT_ID=-5101776367\n", encoding="utf-8")
    monkeypatch.setenv("OMNI_TEST_GROUP_ENV_FILE", str(profile))
    monkeypatch.setenv("OMNI_TEST_CHAT_ID", "-6000000000")

    assert resolver.group_profile_value("OMNI_TEST_CHAT_ID", tmp_path) == "-6000000000"
    assert resolver.group_profile_int("OMNI_TEST_CHAT_ID", tmp_path) == -6000000000


def test_env_or_dotenv_value_reads_dotenv_file(monkeypatch, tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    dotenv = tmp_path / ".env"
    dotenv.write_text("TELEGRAM_WEBHOOK_SECRET='dotenv-secret'\n", encoding="utf-8")
    monkeypatch.setenv("OMNI_TEST_DOTENV_FILE", str(dotenv))
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)

    assert resolver.env_or_dotenv_value("TELEGRAM_WEBHOOK_SECRET", tmp_path) == "dotenv-secret"


def test_telegram_webhook_secret_token_falls_back_to_settings(monkeypatch, tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("OMNI_TEST_DOTENV_FILE", str(tmp_path / "missing.env"))
    system_settings = tmp_path / "packages" / "conf" / "settings.yaml"
    system_settings.parent.mkdir(parents=True)
    system_settings.write_text(
        'telegram:\n  webhook_secret_token: "settings-secret"\n',
        encoding="utf-8",
    )

    assert resolver.telegram_webhook_secret_token(tmp_path) == "settings-secret"


def test_normalize_telegram_session_partition_mode_aliases() -> None:
    resolver = _load_resolver_module()

    assert resolver.normalize_telegram_session_partition_mode("chat-thread-user") == (
        "chat_thread_user"
    )
    assert resolver.normalize_telegram_session_partition_mode("chatuser") == "chat_user"
    assert resolver.normalize_telegram_session_partition_mode("invalid-mode") is None


def test_telegram_session_partition_mode_prefers_env(monkeypatch, tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    system_settings = tmp_path / "packages" / "conf" / "settings.yaml"
    system_settings.parent.mkdir(parents=True)
    system_settings.write_text('telegram:\n  session_partition: "chat_user"\n', encoding="utf-8")

    monkeypatch.setenv("OMNI_AGENT_TELEGRAM_SESSION_PARTITION", "chat_thread_user")
    assert resolver.telegram_session_partition_mode(tmp_path) == "chat_thread_user"


def test_session_partition_mode_from_runtime_log_reads_json_partition_mode(tmp_path: Path) -> None:
    resolver = _load_resolver_module()

    log_file = tmp_path / "runtime.log"
    log_file.write_text(
        'INFO telegram command reply json summary json_partition_mode="chat_thread_user"\n',
        encoding="utf-8",
    )

    assert resolver.session_partition_mode_from_runtime_log(log_file) == "chat_thread_user"
