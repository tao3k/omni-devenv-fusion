{ lib, ... }:
{
  config = {
    files = lib.mkMerge [
      { }
    ];
  };
}
