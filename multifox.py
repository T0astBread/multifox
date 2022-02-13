#! /usr/bin/env nix-shell
#! nix-shell -p python3 python39Packages.click -i python3

"""
multifox helps you launch and manage mutliple instances of Firefox
and the Tor Browser.

This module contains all bundled commands.
"""

import json
import os
import subprocess  # nosec  # It's okay to launch processes.

import click


class BrokenConfigException(click.ClickException):
    """BrokenConfigException marks a broken profile config."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken config: {message}"

    def __str__(self):
        return self.message


class BrokenProfileException(click.ClickException):
    """BrokenProfileException marks a broken profile."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken profile: {message}"

    def __str__(self):
        return self.message


def read_profile_config(config_path):
    """
    read_profile_config reads and validates the profile-config.json
    file of the config at the given path.
    """
    with open(
        os.path.join(config_path, "profile-config.json"), "r", encoding="utf-8"
    ) as f:
        config = json.load(f)
        if "program" not in config or config["program"] == "":
            raise BrokenConfigException('"program" not set in config.json')
        return config


def read_profile_info(profile_path):
    """
    read_profile_ifo reads and validates the profile.json file of the
    profile at the given path.
    """
    with open(os.path.join(profile_path, "profile.json"), "r", encoding="utf-8") as f:
        profile = json.load(f)
        if "program" not in profile or profile["program"] == "":
            raise BrokenProfileException('"program" not set in profile.json')
        return profile


def with_profile_home(profile_path, env):
    """
    with_profile_home returns a copy of the given environment
    variables that causes browsers to create their profiles under the
    given path.
    """
    new_env = dict(env)
    new_env["HOME"] = profile_path
    return new_env


@click.group(add_help_option=False)
@click.help_option("--help", "-h", help="Show this message and exit")
def multifox():
    """
    Launch and manage mutliple instances of Firefox and the Tor
    Browser.
    """
    return


@multifox.command(add_help_option=False)
@click.help_option("--help", "-h", help="Show this message and exit")
@click.argument(
    "config-path",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.argument(
    "profile-path", type=click.Path(file_okay=False, writable=True, resolve_path=True)
)
def init_profile(config_path, profile_path):
    """
    Instantiate a profile from the given config

    The given config is not automatically applied but only used to
    determine the browser program to run.
    """
    config = read_profile_config(config_path)
    os.makedirs(profile_path, exist_ok=True)
    with open(os.path.join(profile_path, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(config, f)

    # Profile configs are assumed to be trusted, so executing
    # arbitrary programs from a profile config is okay.
    subprocess.run(  # nosec
        [config["program"], "--headless", "--screenshot", "/dev/null", "about:blank"],
        env=with_profile_home(profile_path, os.environ),
        check=True,
    )


@multifox.command(add_help_option=False)
@click.help_option("--help", "-h", help="Show this message and exit")
@click.argument(
    "config-path", type=click.Path(exists=True, file_okay=False, resolve_path=True)
)
@click.argument(
    "profile-path",
    type=click.Path(exists=True, file_okay=False, writable=True, resolve_path=True),
)
def apply_profile_config(
    config_path, profile_path
):  # pylint: disable=unused-argument # Will be implemented.
    """Apply a config to a profile"""
    click.echo("Not implemented yet")


@multifox.command(add_help_option=False)
@click.help_option("--help", "-h", help="Show this message and exit")
@click.argument(
    "profile-path",
    type=click.Path(exists=True, file_okay=False, writable=True, resolve_path=True),
)
@click.argument("args", nargs=-1)
def launch_browser(profile_path, args):
    """Start a browser on a specific profile"""
    profile = read_profile_info(profile_path)

    # Profile configs are assumed to be trusted, so executing
    # arbitrary programs from a profile config is okay.
    subprocess.run(  # nosec
        [profile["program"]] + list(args),
        env=with_profile_home(profile_path, os.environ),
        check=True,
    )


if __name__ == "__main__":
    multifox()
