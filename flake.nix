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
  };

  outputs =
    {
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }@inputs:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;
          inherit (inputs.omnibus.flake.inputs) nix-filter;
          omni-core-rs = (
            pkgs.callPackage ./assets/nix/packages/omni-core-rs.nix {
              inherit nix-filter;
            }
          );

          hacks = pkgs.callPackage pyproject-nix.build.hacks { };

          hack-overlay = final: prev: {
            # Adapt torch from nixpkgs
            omni-core-rs = hacks.nixpkgsPrebuilt {
              from = omni-core-rs;
              prev = prev.omni-core-rs;
            };
          };
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
              hack-overlay
              (final: prev: {
                # Fix pypika build with setuptools
                pypika = prev.pypika.overrideAttrs (old: {
                  nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
                    final.setuptools
                  ];
                });
                # Fix hatchling editable build with editables
                hatchling = prev.hatchling.overrideAttrs (old: {
                  propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [
                    final.editables
                  ];
                });
              })
            ]
          )
      );
    in
    {
      packages = forAllSystems (system: {
        omni-core-rs = pythonSets.${system}.omni-core-rs;
        default = (
          pythonSets.${system}.mkVirtualEnv "omni-dev-fusion-env" workspace.deps.default
          // { }
        );
      });
    };
}
