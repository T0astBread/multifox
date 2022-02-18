with (import <nixpkgs> { });
let
  pythonPackages = pkgs: with pkgs; [
    # production dependencies
    click

    # dev dependencies
    bandit
    black
    mypy
    pylint
    pytest
  ];
  pythonWithPackages = python3.withPackages pythonPackages;
in
mkShell {
  buildInputs = [
    pythonWithPackages
  ];
  packages = pythonPackages python39Packages;
  shellHook = ''
    export PATH=$PATH:${pkgs.firefox}/bin:${pkgs.torbrowser}/bin
  '';
}
