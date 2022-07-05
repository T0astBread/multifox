with (import <nixpkgs> { });
let
  pythonPackages = pkgs: with pkgs; [
    # production dependencies
    click
    pygobject3
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

    gtk3
    gnome.zenity
    gobject-introspection
  ];
  packages = pythonPackages python39Packages;
  shellHook = ''
    export PATH=$PATH:${pkgs.firefox}/bin:${pkgs.tor-browser-bundle-bin}/bin
  '';
}
