{
  description = "Nix flake for omni-dev-fusion project";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    omnibus.url = "github:tao3k/omnibus";

    nci.url = "github:90-008/nix-cargo-integration";
    nci.inputs.nixpkgs.follows = "nixpkgs";
    parts.url = "github:hercules-ci/flake-parts";
    parts.inputs.nixpkgs-lib.follows = "nixpkgs";
  };

  outputs =
    inputs:
    let
      inherit (inputs.nixpkgs) lib;
      systems = lib.systems.flakeExposed;
    in
    inputs.parts.lib.mkFlake
      {
        inherit inputs;
      }
      {
        inherit systems;
        debug = true;
        _module.args.workspaceRoot = ./.;
        imports = [
          inputs.nci.flakeModule
          ./assets/nix/modules/flake-parts/omni-core-rs.nix
          ./assets/nix/modules/flake-parts/omni-dev-fusion.nix
        ];
      };

}
