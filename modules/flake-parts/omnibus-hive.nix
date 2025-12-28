{
  inputs,
  lib,
  config,
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
    omnibus.pops.hive = mkOption {
      type = types.either (lib.types.attrsOf lib.types.unspecified) (
        types.functionTo (lib.types.attrsOf lib.types.unspecified)
      );
      default = { };
      apply =
        x:
        let
          hive =
            l:
            (inputs.omnibus.pops.hive.setHosts (
              ((
                (inputs.omnibus.pops.load {
                  inputs = {
                    inherit inputs;
                  };
                }).addLoadExtender
                { load = l; }
              ).exports.default
              )
            ));
        in
        if isFunction x then x hive else hive x;
    };
  };
  config = mkMerge [
    (mkIf (config.omnibus.pops.hive != { }) {
      flake = {
        inherit (config.omnibus.pops.hive.exports)
          nixosConfigurations
          homeConfigurations
          darwinConfigurations
          colmenaHive
          ;
      };
    })
  ];
}
