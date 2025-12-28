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

  genLefthook =
    (config.omnibus.ops.mkNixago initConfigs.nixago-lefthook)
      (removeTreefmt initConfigs.lefthook.default)
      initConfigs.lefthook.nix
      initConfigs.lefthook.shell;
  genConform = (config.omnibus.ops.mkNixago initConfigs.nixago-conform);
in
{
  config = {
    packages =
      genLefthook.__passthru.packages
      ++ [
      ]
      ++ genConform.__passthru.packages;
    enterShell = ''
      ${genLefthook.shellHook}
      ${genConform.shellHook}
    '';
    # perSystem = {...}:{
    #   devenv.shells.default = {
    #     enterShell = ''
    #       ${config.omnibus.ops.mkNixago initConfigs.nixago-lefthook}
    #     '';
    #   };
    # };
  };
}
