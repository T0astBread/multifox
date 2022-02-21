with (import <nixpkgs> { });
let
  pythonPackages = pkgs: with pkgs; [
    # production dependencies
    click
    pyyaml

    # dev dependencies
    bandit
    black
    mypy
    pip
    pylint
    pytest
    virtualenv
  ];
  pythonWithPackages = python3.withPackages pythonPackages;
in
mkShell {
  buildInputs = [
    pythonWithPackages

    gnome.zenity
  ];
  packages = pythonPackages python39Packages;
  shellHook = ''
    export PATH=$PATH:${pkgs.firefox}/bin:${pkgs.torbrowser}/bin
  '';
}
