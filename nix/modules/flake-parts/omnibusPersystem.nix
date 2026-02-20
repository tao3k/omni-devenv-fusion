{
  lib,
  flake-parts-lib,
  inputs,
  ...
}:
let
  inherit (lib)
    types
    mkSubmodule
    mkOption
    ;
  inherit (flake-parts-lib)
    mkPerSystemOption
    ;
in
{
  options.perSystem = mkPerSystemOption (
    { config, pkgs, ... }:
    {
      _file = ./omnibusPersystem.nix.nix;
      options = {
        omnibus.pops = mkOption {
          type = types.submodule {
            options = {
              packages = mkOption {
                type = types.lazyAttrsOf types.unspecified;
                default = { };
                apply =
                  x:
                  (inputs.omnibus.pops.packages {
                    inputs.inputs = {
                      nixpkgs = pkgs;
                    };
                  }).addLoadExtender
                    { load = x; };
                description = ''
                  Packages to be exported with the extensible attribute
                '';
              };
            };
          };
        };
      };
    }
  );
}
