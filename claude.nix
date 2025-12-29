{ lib, config, ... }:
{
  claude.code.enable = true;
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
