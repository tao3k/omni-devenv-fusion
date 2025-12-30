{ __inputs__, __nixpkgs__, ... }:
{
  packages = [
    __inputs__.packages.mcp-inspector
    __nixpkgs__.repomix
  ];
}
