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
        in
        (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope
          (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
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

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythonSet = pythonSets.${system}.overrideScope editableOverlay;
          virtualenv = pythonSet.mkVirtualEnv "omni-dev-fusion-env" workspace.deps.all;
        in
        {
          default = pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
            ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = pythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
        }
      );

      packages = forAllSystems (
        system:
        let
          nixpkgs = inputs.nixpkgs.legacyPackages.${system};
          inherit (inputs.omnibus.flake.inputs) nix-filter;
          omni-core-rs = (
            nixpkgs.callPackage ./units/packages/omni-core-rs.nix {
              inherit nix-filter;
            }
          );
        in
        {
          inherit omni-core-rs;
          default =
            (pythonSets.${system}.mkVirtualEnv "omni-dev-fusion-env" workspace.deps.default)
            .overrideAttrs
              (old: {
                postInstall = ''
                  ln -s ${omni-core-rs}/${nixpkgs.python3Packages.python.sitePackages}/omni_core_rs $out/${nixpkgs.python3Packages.python.sitePackages}/omni_core_rs
                '';
              });
        }
      );
    };
}
