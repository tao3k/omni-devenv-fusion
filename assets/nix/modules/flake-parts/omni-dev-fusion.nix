{
  inputs,
  workspaceRoot,
  self,
  ...
}:

let
  inherit (inputs)
    uv2nix
    nix-filter
    pyproject-nix
    pyproject-build-systems
    ;
in
{
  perSystem =
    {
      pkgs,
      lib,
      system,
      ...
    }:
    let
      workspace = uv2nix.lib.workspace.loadWorkspace { inherit workspaceRoot; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      pythonSets =
        let

          hacks = pkgs.callPackage pyproject-nix.build.hacks { };
          python = pkgs.python3;
          hack-overlay = final: prev: {
            omni-core-rs = hacks.nixpkgsPrebuilt {
              from = self.packages.${system}.omni-core-rs-python-bindings;
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
          );
    in
    {
      packages.default = self.packages.${system}.omni-dev-fusion;
      packages.omni-dev-fusion = pythonSets.mkVirtualEnv "omni-dev-fusion" workspace.deps.default;
    };
}
