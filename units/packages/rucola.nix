{
  lib,
  fetchFromGitHub,
  rustPlatform,
  pkg-config,
  openssl,
  stdenv,
}:

rustPlatform.buildRustPackage rec {
  pname = "rucola";
  version = "0.8.2";

  src = fetchFromGitHub {
    owner = "Linus-Mussmaecher";
    repo = "rucola";
    rev = "v${version}";
    hash = "sha256-Lg/JzB+FFPaIfue4Vwn1X4WNHaK3FSZYHsxy+ZQpbPs=";
  };

  cargoHash = "sha256-4hdG8jBD7zSG0g4H1qfNVNq4ngwRstYeum+eix41W3E=";

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
    mainProgram = "rucola";
  };
}
