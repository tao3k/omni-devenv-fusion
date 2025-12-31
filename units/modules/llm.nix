{
  __inputs__,
  __nixpkgs__,
  pkgs,
  lib,
  ...
}:
let
  system = pkgs.stdenv.hostPlatform.system;
in
{
  packages = [
    __inputs__.packages.mcp-inspector
    __inputs__.packages.backmark
    __inputs__.llm-agents.packages.${system}.claudebox
    __nixpkgs__.repomix
    __nixpkgs__.ast-grep
    __nixpkgs__.spec-kit
  ]
  ++ lib.optionals (system != "aarch64-darwin") [
    __inputs__.llm-agents.packages.${system}.backlog-md
  ];
}
