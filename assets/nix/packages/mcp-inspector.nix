{
  lib,
  buildNpmPackage,
  fetchFromGitHub,
  nodejs,
  jq,
  ...
}:
buildNpmPackage rec {
  pname = "mcp-inspector";
  version = "0.17.1";

  src = fetchFromGitHub {
    owner = "modelcontextprotocol";
    repo = "inspector";
    rev = version;
    hash = "sha256-xiNBMCtDAoNxgB4Vh+m/2hrBBwzzAB9/37J0qsDlSaE=";
  };

  postPatch = ''
    ${jq}/bin/jq '.packages["node_modules/router/node_modules/path-to-regexp"] += {
      resolved: "https://registry.npmjs.org/path-to-regexp/-/path-to-regexp-8.2.0.tgz",
      integrity: "sha512-TdrF7fW9Rphjq4RjrW0Kp2AW0Ahwu9sRGTkS6bvDi0SCwZlEZYmcfDbEsTz8RVk0EHIS/Vd1bv3JhG+1xZuAyQ=="
    }' package-lock.json > package-lock.json.new
    mv package-lock.json.new package-lock.json
    sed -i 's/\.allowExcessArguments()/\.allowExcessArguments?.()/g' cli/src/cli.ts
  '';

  makeWrapperArgs = [
    "--prefix PATH : ${
      lib.makeBinPath [
        nodejs
      ]
    }"
  ];

  dontNpmPrune = true;

  npmDepsHash = "sha256-QuG+RLsduOplFEY92sQC4R7w04Pk/nIIvaQaEHYLzXU=";

  doCheck = false;

  meta = with lib; {
    description = "Visual testing tool for MCP servers";
    homepage = "https://github.com/modelcontextprotocol/inspector";
    license = licenses.mit;
    maintainers = [ ];
    platforms = platforms.all;
  };
}
