{
  lib,
  stdenv,
  python3Packages,
  rustPlatform,
  maturin,
  pkg-config,
  openssl,
  libiconv,
  python313,
  protobuf,
  nix-filter,
  ...
}:

let
  root = ../..;
  pname = "omni-core-rs";
  version = "0.1.0";

  filteredSrc = nix-filter.lib.filter {
    inherit root;
    include = [
      # Rust workspace
      "Cargo.toml"
      "Cargo.lock"

      # All Rust crates
      "packages/rust/crates"
      "packages/rust/bindings/python"
    ];
  };
in
python3Packages.buildPythonPackage {
  inherit pname version;
  name = pname;
  pyproject = true;

  src = filteredSrc;

  # Use maturin to build the Rust extension module
  buildInputs = [
    openssl
    python3Packages.hatchling
    python3Packages.hatch-vcs
  ]
  ++ lib.optionals stdenv.hostPlatform.isDarwin [
    libiconv
  ];

  # Vendor dependencies from the workspace
  cargoDeps = rustPlatform.fetchCargoVendor {
    pname = "omni-core-rs";
    version = "0.1.0";
    src = filteredSrc;
    hash = "sha256-KIUmOay2RVLkQvZYM6X5+ufEXNbDcHj6faRmxhg40Ww=";
  };

  build-system = [ rustPlatform.maturinBuildHook ];

  nativeBuildInputs = [
    rustPlatform.cargoSetupHook
  ];

  preConfigure = ''
    cd packages/rust/bindings/python
  '';

  env = {
    PYO3_PYTHON = "${python313}/bin/python3.13";
    OPENSSL_NO_VENDOR = 1;
    PROTOC = "${protobuf}/bin/protoc";
  };

  # Don't run tests during build
  doCheck = false;

  meta = {
    description = "Rust core bindings for Omni DevEnv Fusion";
    longDescription = ''
      High-performance Rust bindings providing core functionality for Omni DevEnv:
      - omni-sniffer: Code analysis and context extraction
      - omni-vector: Vector database with LanceDB
      - omni-tags: Tag extraction
      - omni-edit: Structural code editing
      - omni-security: Security scanning
    '';
    homepage = "https://github.com/tao3k/omni-devenv-fusion";
    license = with lib.licenses; [ "apache20" ];
    maintainers = with lib.maintainers; [ "tao3k" ];
    pythonPath = "${python313.sitePackages}";
  };
}
