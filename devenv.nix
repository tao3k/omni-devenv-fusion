{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

let
  nixpkgs-latest = import inputs.nixpkgs-latest {
    system = pkgs.stdenv.hostPlatform.system;
    config = {
      allowUnfree = true;
    };
  };
  nixosModules =
    (inputs.omnibus.pops.nixosProfiles.addLoadExtender {
      load = {
        src = ./modules;
        inputs = {
          nixpkgs = nixpkgs-latest;
          inputs = inputs // {
            nixpkgs = nixpkgs-latest;
          };
        };
      };
    }).exports.default;
in
{
  imports = [
    nixosModules.claude
    nixosModules.flake-parts.omnibus
    nixosModules.files
    nixosModules.lefthook
    nixosModules.python
    #./modules/flake-parts/omnibus-hive.nix
    ({
      config = lib.mkMerge [
        {
          omnibus = {
            inputs = {
              inputs = {
                nixpkgs = pkgs;
                inherit (inputs.omnibus.flake.inputs) nixago;
              };
            };
          };
        }
      ];
    })
  ];
  
  devcontainer.enable = true;
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.just
    nixpkgs-latest.claude-code
    pkgs.secretspec
    pkgs._1password-cli
  ];

  # https://devenv.sh/languages/
  # languages.rust.enable = true;

  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/pre-commit-hooks/
  # git-hooks.hooks.shellcheck.enable = true;
  # git-hooks.hooks.nixfmt.enable = true;
  # See full reference at https://devenv.sh/reference/options/
}
