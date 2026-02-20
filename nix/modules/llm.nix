{
  __inputs__,
  __nixpkgs__,
  inputs,
  pkgs,
  lib,
  ...
}:
let
  system = pkgs.stdenv.hostPlatform.system;
in
{
  packages = [
    inputs.worktrunk.packages.${system}.worktrunk
    __inputs__.packages.mcp-inspector
    __inputs__.packages.backmark
    # ``__inputs__.llm-agents.packages.${system}.claudebox
    __nixpkgs__.repomix
    __nixpkgs__.ast-grep
    __nixpkgs__.spec-kit
    # __nixpkgs__.claude-code
    __inputs__.llm-agents.packages.${system}.claude-code
    # __inputs__.llm-agents.packages.${system}.cursor-agent
    # __nixpkgs__.playwright-driver.browsers
    __inputs__.llm-agents.packages.${system}.codex
    __inputs__.llm-agents.packages.${system}.gemini-cli
  ]
  ++ lib.optionals (system != "aarch64-darwin") [
    __inputs__.llm-agents.packages.${system}.backlog-md
  ];

  env = {
    # PLAYWRIGHT_BROWSERS_PATH = "${__nixpkgs__.playwright-driver.browsers}";
    # PLAYWRIGHT_LAUNCH_OPTIONS_EXECUTABLE_PATH  = "${__nixpkgs__.playwright-driver.browsers}/chromium-1194/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
  };
}
