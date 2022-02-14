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
from enum import Enum

import click


class ProfileType(Enum):
    """ProfileType marks what program a profile is for."""

    FIREFOX = "firefox"
    TOR_BROWSER = "tor-browser"


class ProfileConfig:
    """
    ProfileConfig holds a profile configuration.

    Profile configurations are basically "templates" for profiles.
    Unlike templates they can be applied to existing profiles as
    well, not just to newly created profiles.
    """

    type: ProfileType
    program: str

    @staticmethod
    def from_json(config_json):
        """
        from_json creates a new ProfileConfig object from a provided
        JSON dictionary.
        """
        config = ProfileConfig()
        if "type" not in config_json:
            raise BrokenConfigException('"type" not set in config.json')
        try:
            config.type = ProfileType(config_json["type"])
        except ValueError as ex:
            raise BrokenConfigException(
                f'"type" must be one of ({enum_synopsis(ProfileType)})'
            ) from ex
        config.program = config.type.value
        return config

    def to_json(self):
        """
        to_json returns a JSON-serializable dict for the data in this
        ProfileConfig.

        Decoding the return value of this method using `from_json`
        results in a ProfileConfig instance that's equivalent to this
        instance.
        """
        return {
            "type": self.type.value,
        }


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


def enum_synopsis(enum) -> str:
    """
    enum_synopsis returns a human-readably overview of an enum's
    values.
    """
    return "|".join([v.value for v in enum])


def read_profile(path):
    """
    read_profile reads and validates a profile-config.json file or
    profile.json file at the given path.
    """
    with open(os.path.join(path, "profile-config.json"), "r", encoding="utf-8") as f:
        config_json = json.load(f)
        return ProfileConfig.from_json(config_json)


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
    config = read_profile(config_path)
    os.makedirs(profile_path, exist_ok=True)
    with open(
        os.path.join(profile_path, "profile-config.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(config.to_json(), f)

    subprocess.run(
        [config.program, "--headless", "--screenshot", "/dev/null", "about:blank"],
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
    profile = read_profile(profile_path)

    subprocess.run(
        [profile.program] + list(args),
        env=with_profile_home(profile_path, os.environ),
        check=True,
    )


if __name__ == "__main__":
    multifox()
