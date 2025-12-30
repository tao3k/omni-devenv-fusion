{
  inputs,
  __inputs__,
  pkgs,
  config,
  lib,
}:
let
  inherit (inputs.omnibus.inputs.dmerge) prepend;
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
          # Remove treefmt from commands
          commands = builtins.removeAttrs lefthook.data.pre-commit.commands [ "treefmt" ];
          # Exclude CHANGELOG.md from typos (false positives from commit hashes)
          exclude = prepend [ "CHANGELOG.md" ];
        };
      } initConfigs.lefthook.nix initConfigs.lefthook.shell;
    }
    {
      name = "conform";
      gen = (config.omnibus.ops.mkNixago initConfigs.nixago-conform) initConfigs.conform.default;
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
    # perSystem = {...}:{
    #   devenv.shells.default = {
    #     enterShell = ''
    #       ${config.omnibus.ops.mkNixago initConfigs.nixago-lefthook}
    #     '';
    #   };
    # };
  };
}
