{ lib, config, ... }:
{
  claude.code.enable = true;
  claude.code.hooks = {
    PostToolUse = {
      command = ''
        cd "$DEVENV_ROOT" && lefthook run pre-commit
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
