{
  lib,
  fetchFromGitHub,
  rustPlatform,
  pkg-config,
  openssl,
  stdenv,
}:

rustPlatform.buildRustPackage rec {
  pname = "iwe-org/iwe";
  version = "0.6.1";

  src = fetchFromGitHub {
    owner = "iwe-org";
    repo = "iwe";
    rev = "e10cb405e189eea896f89f0020fb2edafa0171e3";
    hash = "sha256-PhRrCWE2mebjs0V+8GbXEZzTKgsPZEgC7OhaQwJdfKY=";
  };

  cargoHash = "sha256-PqINghZ88FsXj4HEFp0ugFH30lbQfBcoiv86PPOCzLI=";

  nativeBuildInputs = [
    pkg-config
    openssl
  ];

  buildInputs = [
    openssl
  ]
  ++ lib.optionals stdenv.isLinux [ ]
  ++ lib.optionals stdenv.isDarwin [ ];

  doCheck = false;

  meta = with lib; {
    description = "Terminal-based markdown note manager";
    homepage = "https://github.com/Linus-Mussmaecher/rucola";
    license = licenses.gpl3Only;
    maintainers = [ ];
    mainProgram = "iwe";
  };
}
