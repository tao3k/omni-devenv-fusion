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
    # __nixpkgs__.playwright-driver.browsers
  ]
  ++ lib.optionals (system != "aarch64-darwin") [
    __inputs__.llm-agents.packages.${system}.backlog-md
  ];

  env = {
    # PLAYWRIGHT_BROWSERS_PATH = "${__nixpkgs__.playwright-driver.browsers}";
    # PLAYWRIGHT_LAUNCH_OPTIONS_EXECUTABLE_PATH  = "${__nixpkgs__.playwright-driver.browsers}/chromium-1194/chrome-mac/Chromium.app/Contents/MacOS/Chromium";
  };
}
