{
  lib,
  config,
  pkgs,
  __inputs__,
  ...
}:
let
  system = pkgs.stdenv.hostPlatform.system;
in
{
  packages = [
    __inputs__.llm-agents.packages.${system}.claude-code
  ];
  claude.code.enable = true;
  claude.code.env = {
    MINIMAX_API_KEY = config.secretspec.secrets.MINIMAX_API_KEY;
    ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic";
    ANTHROPIC_AUTH_TOKEN = config.secretspec.secrets.MINIMAX_API_KEY;
    API_TIMEOUT_MS = "2000000";
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"; # Note: Convert to string
    ANTHROPIC_MODEL = "MiniMax-M2.1";
    ANTHROPIC_SMALL_FAST_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_SONNET_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_OPUS_MODEL = "MiniMax-M2.1";
    ANTHROPIC_DEFAULT_HAIKU_MODEL = "MiniMax-M2.1";
  };
  claude.code.hooks = {
    # PostToolUse = {
    #   command = ''
    #     bash -c 'cd "$DEVENV_ROOT" && source "$(ls -t .direnv/devenv-profile*.rc 2>/dev/null | head -1)" && lefthook run pre-commit'
    #   '';
    #   matcher = "^(Edit|MultiEdit|Write)$";
    # };
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
    # nixos = {
    #   type = "stdio";
    #   command = "nix";
    #   args = [
    #     "run"
    #     "github:utensils/mcp-nixos"
    #     "--"
    #   ];
    # };
    MiniMax = {
      type = "stdio";
      command = "uvx";
      args = [ "minimax-coding-plan-mcp" ];
      env = {
        MINIMAX_API_KEY = config.secretspec.secrets.MINIMAX_API_KEY;
        MINIMAX_MCP_BASE_PATH = "${config.devenv.root}/.minimax-output";
        MINIMAX_API_HOST = "https://api.minimax.io";
        MINIMAX_API_RESOURCE_MODE = "url";
      };
    };

    omniAgent = {
      type = "stdio";
      # url = "http://0.0.0.0:3002/sse";
      command = "omni";
      args = [
        "mcp"
        "--transport"
        "stdio"
        # "--port"
        # "3002"
      ];
      env = {
        OMNI_UX_MODE = "headless";
        MINIMAX_API_KEY = config.secretspec.secrets.MINIMAX_API_KEY;
      };
    };
  };
}
