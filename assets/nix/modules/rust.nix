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
    pkgs.maturin
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
    # Fix PyO3 extension module linking for cargo test
    # Add Python library path for macOS and Linux
    PYTHON_LIB_PATH = "${config.languages.python.package}/lib";
    DYLD_LIBRARY_PATH = "${config.languages.python.package}/lib:${pkgs.openssl.out}/lib:''\${DYLD_LIBRARY_PATH:-}";
    LD_LIBRARY_PATH = "${config.languages.python.package}/lib:${pkgs.openssl.out}/lib:''\${LD_LIBRARY_PATH:-}";
  };
}
