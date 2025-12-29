{ lib, config, ... }:
{
  claude.code.enable = true;
  claude.code.env = {
    ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic";
    ANTHROPIC_AUTH_TOKEN = config.secretspec.secrets.MINIMAX_API_KEY;
    API_TIMEOUT_MS = "2000000";
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"; # 注意：转换为字符串
    ANTHROPIC_MODEL = "MiniMax-M2.1";
    ANTHROPIC_SMALL_FAST_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_SONNET_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_OPUS_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_HAIKU_MODEL = "MiniMax-M2.1";
  };
  claude.code.hooks = {
    PostToolUse = {
      command = ''
        bash -c 'cd "$DEVENV_ROOT" && source "$(ls -t .direnv/devenv-profile*.rc 2>/dev/null | head -1)" && lefthook run pre-commit'
      '';
      matcher = "^(Edit|MultiEdit|Write)$";
    };
  };
  claude.code.mcpServers = {
    # Local devenv MCP server
    devenv = {
      type = "stdio";
      command = "devenv";
      args = [ "mcp" ];
      env = {
        DEVENV_ROOT = config.devenv.root;
      };
    };
    nixos = {
      type = "stdio";
      command = "nix";
      args = [
        "run"
        "github:utensils/mcp-nixos"
        "--"
      ];
    };
  };
}
