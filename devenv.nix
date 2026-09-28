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
    package = pkgs.python312.withPackages (ps: [
      ps.numpy
      ps.pandas
      
    ]);
    venv.enable = true;
    uv.enable = true;

  };
  packages = with pkgs; [
    stdenv.cc.cc.lib
    zlib
    # # Demo AEP: numpy/scipy/ pandas / scikit-learn (ver README > DEMO AEP).
    # python312Packages.numpy
    # python312Packages.scikit-learn
  ];
  enterShell = ''
    source .venv/bin/activate
    echo "$(tput bold)hi! from $(tput setaf 118)pyhton$(tput sgr0)"
  '';
}
