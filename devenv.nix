{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  env = {
    name = "tesis";
  };
  languages.python = {
    enable = true;
    package = pkgs.python312;
    venv.enable = true;
    uv.enable = true;
  };
  packages = with pkgs; [
    stdenv.cc.cc.lib
    zlib
  ];
  enterShell = ''
    source .venv/bin/activate
    echo "$(tput bold)hi! from $(tput setaf 118)pyhton$(tput sgr0)"
  '';
}
