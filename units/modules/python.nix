{ __inputs__, ... }:
{
  packages = [
    __inputs__.packages.mcp-inspector
  ];
  languages.python = {
    enable = true;
    venv.enable = true;
    # directory = "../.";
    uv = {
      enable = true;
      # package = inputs.nixpkgs.uv;
      sync.enable = true;
    };
  };
}
