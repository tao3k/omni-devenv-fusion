{
  inputs,
  __inputs__,
  pkgs,
  config,
  lib,
}:
let
  inherit (inputs.omnibus.inputs.flops.inputs.dmerge) prepend append merge;
  initConfigs =
    (inputs.omnibus.units.configs {
      inputs = {
        inputs = {
          nixpkgs = __inputs__.nixpkgs-latest;
          inherit (inputs.omnibus.flake.inputs) git-hooks;
        };
      };
    }).exports.default;

  lefthook = initConfigs.lefthook;

  # Project scopes shared across conform and cog
  # Maps to: agent/how-to/git-workflow.md
  project-scopes = [
    "nix" # Infrastructure: devenv.nix, modules
    "mcp" # Application: mcp-server logic
    "router" # Logic: Tool routing & intent
    "docs" # Documentation
    "cli" # Tooling: justfile, lefthook
    "deps" # Dependency management
    "ci" # GitHub Actions, DevContainer
    "data" # JSONL examples, assets
    "version" # Version bump commits
    "claude" # Claude configuration
    "git-workflow" # Git workflow documentation
    "mcp-core" # Core MCP server modules
    "inference" # AI inference engine
    "orchestrator" # Orchestrator module
    "git-ops" # Git operations tools
  ];
  # Define generator configurations
  generators = [
    {
      name = "lefthook";
      gen =
        (config.omnibus.ops.mkNixago initConfigs.nixago-lefthook)
          {
            data = {
              commit-msg = lefthook.default.data.commit-msg;
              # Remove unnecessary commands from default pre-commit
              commands = builtins.removeAttrs lefthook.default.data.pre-commit.commands [
                "treefmt" # We use nixfmt instead
                "hunspell" # Vale handles documentation
                "typos" # Vale handles spelling
              ];
              # Add ruff for Python formatting
              "format-python" = {
                glob = "*.py";
                run = "ruff format {staged_files}";
              };
              # Add Vale for documentation linting
              "check-docs" = {
                glob = "*.md";
                run = "vale {staged_files}";
              };
            };
          }
          initConfigs.lefthook.nix
          initConfigs.lefthook.shell
          initConfigs.lefthook.prettier;
    }
    {
      name = "conform";
      gen =
        (config.omnibus.ops.mkNixago initConfigs.nixago-conform)
          initConfigs.conform.default
          {
            data.commit = {
              conventional = {
                scopes = append project-scopes;
              };
            };
          };
    }
    {
      name = "cog";
      gen =
        (config.omnibus.ops.mkNixago initConfigs.nixago-cog) initConfigs.cog.default
          {
            data = {
              scopes = project-scopes;
              changelog = {
                path = "CHANGELOG.md";
                template = "remote";
                remote = "github.com";
                repository = "omni-devenv-fusion";
                owner = "tao3k";
                authors = [
                  {
                    username = "gtrunsec";
                    signature = "Guangtao";
                  }
                ];
              };
            };
          };
    }
  ];

  # Generate all hooks using map
  generatedHooks = map (g: g.gen) generators;
in
{
  config = {
    packages = lib.flatten (map (g: g.__passthru.packages) generatedHooks);
    enterShell = lib.concatMapStringsSep "\n" (g: g.shellHook) generatedHooks;
  };
}
