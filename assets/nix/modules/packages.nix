{
  pkgs,
  config,
  __inputs__,
  ...
}:
let
  inherit (__inputs__) nixpkgs-latest;
in
{
  packages = [
    nixpkgs-latest.eza

    nixpkgs-latest.just
    nixpkgs-latest.glow
    nixpkgs-latest.google-cloud-sdk

    nixpkgs-latest.nickel
  ];
}
