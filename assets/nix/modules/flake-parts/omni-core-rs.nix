{ workspaceRoot, inputs, ... }:
let
  inherit (inputs.omnibus.flake.inputs) nix-filter;
in
{
  perSystem =
    {
      pkgs,
      config,
      lib,
      ...
    }:
    {
      nci.projects."omni-core-rs" = {
        path = workspaceRoot;
        # export all crates (packages and devshell) in flake outputs
        # alternatively you can access the outputs and export them yourself
        export = true;
        depsDrvConfig = {
          mkDerivation = {
            buildInputs = [
              pkgs.pkg-config
              pkgs.openssl
            ];
          };
          env = {
            PROTOC = "${pkgs.protobuf}/bin/protoc";
          };
        };
      };
      # configure crates
      nci.crates = {
        # "omni-vector" = {
        #   depsDrvConfig = {
        #     # mkDerivation.buildInputs = [pkgs.pkg-config pkgs.openssl];
        #     env = {
        #       PROTOC = "${pkgs.protobuf}/bin/protoc";
        #       OPENSSL_DIR = lib.getDev pkgs.openssl;
        #       OPENSSL_LIB_DIR = "${lib.getLib pkgs.openssl}/lib";
        #       OPENSSL_NO_VENDOR = 1;
        #     };
        #   };
        # look at documentation for more options
        # };
      };
      packages.omni-core-rs-python-bindings =
        pkgs.callPackage ../../packages/omni-core-rs.nix
          {
            inherit nix-filter;
            inherit workspaceRoot;
            cargoDeps =
              config.nci.outputs."omni-core-rs".packages.release.config.rust-cargo-vendor.vendoredSources;
            version = config.nci.outputs."omni-core-rs".packages.release.config.version;
          };
    };
}
