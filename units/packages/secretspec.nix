{
  lib,
  rustPlatform,
  fetchCrate,
  pkg-config,
  dbus,
  nix-update-script,
}:

rustPlatform.buildRustPackage (finalAttrs: {
  pname = "secretspec";
  version = "0.6.0";

  src = fetchCrate {
    inherit (finalAttrs) pname version;
    hash = "sha256-/lxfu6PKjfJ9Siz7slZzaaeSkPJawxcxWvhmn+il9gs=";
  };

  cargoHash = "sha256-PnsPR2QV8MpCeRJ/D87VloJym6WezYahZ8ph67ZaSGs=";

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ dbus ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Declarative secrets, every environment, any provider";
    homepage = "https://secretspec.dev";
    license = with lib.licenses; [ asl20 ];
    maintainers = with lib.maintainers; [
      domenkozar
      sandydoo
    ];
    mainProgram = "secretspec";
  };
})
