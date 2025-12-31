{
  __inputs__,
  __nixpkgs__,
  pkgs,
  ...
}:
{
  packages = [
    __inputs__.packages.mcp-inspector
    __inputs__.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.claudebox
    __inputs__.llm-agents.packages.${pkgs.stdenv.hostPlatform.system}.backlog-md
    __nixpkgs__.repomix
    __nixpkgs__.ast-grep
  ];
}
