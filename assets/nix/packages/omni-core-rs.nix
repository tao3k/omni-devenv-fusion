{
  lib,
  stdenv,
  symlinkJoin,
  python3Packages,
  rustPlatform,
  maturin,
  pkg-config,
  openssl,
  libiconv,
  python3,
  protobuf,
  nix-filter,
  workspaceRoot,
  cargoDeps,
  version,
  ...
}:

let
  pname = "omni-core-rs";
  filteredSrc = nix-filter.lib.filter {
    root = workspaceRoot;
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
  cargoDeps = symlinkJoin {
    name = "${pname}-cargo-deps";
    paths = [
      cargoDeps
      filteredSrc
    ];
  };

  build-system = [ rustPlatform.maturinBuildHook ];

  nativeBuildInputs = [
    pkg-config
    rustPlatform.cargoSetupHook
  ];

  preConfigure = ''
    cd packages/rust/bindings/python
  '';

  env = {
    PYO3_PYTHON = "${python3}/bin/python3";
    PROTOC = "${protobuf}/bin/protoc";
    OPENSSL_DIR = lib.getDev openssl;
    OPENSSL_LIB_DIR = "${lib.getLib openssl}/lib";
    OPENSSL_NO_VENDOR = 1;
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
    homepage = "https://github.com/tao3k/omni-dev-fusion";
    license = with lib.licenses; [ "apache20" ];
    maintainers = with lib.maintainers; [ "tao3k" ];
    pythonPath = "${python3.sitePackages}";
  };
}
