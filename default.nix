{ lib
, pkgs
, buildPythonApplication
, click
, pyyaml
}:

buildPythonApplication rec {
  pname = "multifox";
  version = "0.0.1";

  src = ./.; # Nix doesn't like "." or "./" but "./." works. 🙃

  propagatedBuildInputs = [
    # Python packages
    click
    pyyaml
  ] ++ (with pkgs; [
    # Other OS packages
    gnome.zenity
  ]);

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
