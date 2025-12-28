{
  inputs,
  lib,
  config,
  pkgs,
  ...
}:
let
  inherit (lib)
    types
    mkOption
    mkMerge
    mkIf
    isFunction
    ;
in
{
  options = {
    omnibus = mkOption {
      type = types.either (lib.types.attrsOf lib.types.unspecified) (
        types.functionTo (lib.types.attrsOf lib.types.unspecified)
      );
      default = { };
      apply =
        x:
        let
          omnibus =
            l:
            (
              (inputs.omnibus.pops.self.addLoadExtender ({
                load.inputs = {
                  inherit inputs;
                };
              })).addLoadExtender
              { load = l; }
            ).exports.default;
        in
        if isFunction x then x omnibus else omnibus x;
    };
  };
}
