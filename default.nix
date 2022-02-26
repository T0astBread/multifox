{ lib
, pkgs
, buildPythonApplication
, click
, gobject-introspection
, gtk3
, pygobject3
, pyyaml
, wrapGAppsHook
}:

buildPythonApplication rec {
  pname = "multifox";
  version = "0.0.1";

  src = ./.; # Nix doesn't like "." or "./" but "./." works. 🙃

  buildInputs = [
    gobject-introspection
    gtk3
    wrapGAppsHook
  ];

  propagatedBuildInputs = [
    # Python packages
    click
    pygobject3
    pyyaml
  ] ++ (with pkgs; [
    # Other OS packages
    gnome.zenity
  ]);

  # The package doesn't have tests right now and apparently that
  # causes the build to fail, so deactivate the check phase.
  #
  # TODO: When there are tests, enable the check phase again.
  doCheck = false;

  postInstall = ''
    completions_path="$out/share/fish/vendor_completions.d"
    mkdir -p "$completions_path"
    prev_path="$PATH"
    PATH="$out/bin:$PATH"
    _MULTIFOX_COMPLETE=fish_source multifox > $completions_path/multifox.fish
    PATH="$prev_path"
  '';

  meta = with lib; {
    description = "multifox helps you launch and manage multiple instances of Firefox and the Tor Browser.";
    homepage = "https://github.com/t0astbread/multifox";
  };
}
