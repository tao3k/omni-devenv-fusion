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
    pkgs.protobuf
    nixpkgs-latest.maturin
    pkgs.openssl
    pkgs.pkg-config
    pkgs.libiconv
  ];
  # https://devenv.sh/languages/
  languages.rust = {
    enable = true;
    channel = "nightly";
    # Ensure rust can link python library
    components = [
      "rustc"
      "cargo"
      "clippy"
      "rustfmt"
      "rust-analyzer"
    ];
  };

  env = {
    PYO3_PYTHON = "${config.languages.python.package}/bin/python";
    PROTOC = "${pkgs.protobuf}/bin/protoc";
  };
}
