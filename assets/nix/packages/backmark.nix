{
  lib,
  buildNpmPackage,
  fetchFromGitHub,
  nodejs,
  jq, # 如果后续需要修补 package-lock.json，则保留此项
  ...
}:

buildNpmPackage rec {
  pname = "backmark";

  version = "unstable-2025-12-20";

  src = fetchFromGitHub {
    owner = "Grazulex";
    repo = "backmark";
    rev = "29576fa429d319ec1c2c14c3f9381951f613f447";
    hash = "sha256-p60pblso25N3mxR1E79Guzpw6jTJAIAvxluvd+JTx7I=";
  };

  npmDepsHash = "sha256-856OoNjh2IiX1NnarjWAJ+PWFC3YfjilNT4HJAqbj0o=";

  dontNpmPrune = true;

  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath [ nodejs ]}"
  ];

  doCheck = false;

  meta = with lib; {
    description = "Backmark - A CLI tool"; # 请根据实际情况调整描述
    homepage = "https://github.com/Grazulex/backmark";
    license = licenses.mit; # 请核实仓库的 License
    maintainers = [ ];
    mainProgram = "backmark"; # 构建完成后 bin 目录下的可执行文件名
  };
}
