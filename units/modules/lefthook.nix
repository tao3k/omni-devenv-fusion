{
  inputs,
  __inputs__,
  pkgs,
  config,
  lib,
}:
let
  inherit (inputs.omnibus.inputs.flops.inputs.dmerge) prepend append;
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

  # Define generator configurations
  generators = [
    {
      name = "lefthook";
      gen = (config.omnibus.ops.mkNixago initConfigs.nixago-lefthook) {
        data = {
          # Remove unnecessary commands from default pre-commit
          commands = builtins.removeAttrs lefthook.default.data.pre-commit.commands [
            "treefmt" # We use nixfmt instead
            "hunspell" # Vale handles documentation
            "typos" # Vale handles spelling
          ];
          # Add Vale for documentation linting
          "check-docs" = {
            glob = "*.md";
            run = "vale {staged_files}";
          };
        };
      } initConfigs.lefthook.nix initConfigs.lefthook.shell;
    }
    {
      name = "conform";
      gen =
        (config.omnibus.ops.mkNixago initConfigs.nixago-conform)
          initConfigs.conform.default
          {
            data.commit = {
              conventional = {
                scopes = append [
                  "nix"
                  "mcp"
                  "router"
                  "docs"
                  "cli"
                  "deps"
                  "ci"
                ];
              };
            };
          };
    }
    {
      name = "cog";
      gen =
        (config.omnibus.ops.mkNixago initConfigs.nixago-cog) initConfigs.cog.default
          {
            hook.mode = "copy";
            data = {
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
