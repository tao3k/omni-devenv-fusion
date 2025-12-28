{
  inputs,
  pkgs,
  config,
  lib,
  ...
}:
let
  nixpkgs-latest =
    inputs.nixpkgs-latest.legacyPackages.${pkgs.stdenv.hostPlatform.system};

  initConfigs =
    (inputs.omnibus.units.configs {
      inputs = {
        inputs = {
          nixpkgs = nixpkgs-latest;
          inherit (inputs.omnibus.flake.inputs) git-hooks;
        };
      };
    }).exports.default;

  lefthook = initConfigs.lefthook;

  removeTreefmt = lib.updateManyAttrsByPath [
    {
      path = [
        "data"
        "pre-commit"
        "commands"
      ];
      update = old: builtins.removeAttrs old [ "treefmt" ];
    }
  ];

  # Define generator configurations
  generators = [
    {
      name = "lefthook";
      gen = (config.omnibus.ops.mkNixago initConfigs.nixago-lefthook)
        (removeTreefmt initConfigs.lefthook.default)
        initConfigs.lefthook.nix
        initConfigs.lefthook.shell;
    }
    {
      name = "conform";
      gen = (config.omnibus.ops.mkNixago initConfigs.nixago-conform);
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
