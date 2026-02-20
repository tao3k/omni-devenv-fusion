{
  withSystem,
  config,
  lib,
  inputs,
  system,
  ...
}:
let
  inherit (lib)
    types
    mkOption
    mkMerge
    mkIf
    ;

  omnibusPackages = system: (config.perSystem system).omnibus.pops.packages;
in
{
  imports = [ ./omnibusPersystem.nix ];
  config = mkMerge [
    ({
      flake.overlays.default =
        final: prev:
        withSystem prev.stdenv.hostPlatform.system (
          { config, ... }: config.omnibus.pops.packages.overlays.default
        );
      flake.overlays.composedPackages =
        final: prev:
        withSystem prev.stdenv.hostPlatform.system (
          { config, ... }: config.omnibus.pops.packages.overlays.composedPackages
        );
      perSystem =
        { config, options, ... }:
        {
          config = mkMerge [
            (mkIf options.omnibus.pops.isDefined {
              packages = config.omnibus.pops.packages.exports.derivations;
            })
          ];
        };
    })
  ];

}
