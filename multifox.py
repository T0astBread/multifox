#! /usr/bin/env nix-shell
#! nix-shell -p python3 python39Packages.click python39Packages.pyyaml -i python3

"""
multifox helps you launch and manage mutliple instances of Firefox
and the Tor Browser.

This module contains all bundled commands.
"""

import os
import shutil
import subprocess
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

import click
import yaml


class ProfileType(Enum):
    """ProfileType marks what program a profile is for."""

    FIREFOX = "firefox"
    TOR_BROWSER = "tor-browser"


class ProfileConfiguration:
    """
    ProfileConfiguration describes settings and customizations of a
    browser profile.
    """

    type: ProfileType
    userjs: Optional[str]


def profile_configuration_from_yaml(
    profile_config_yaml,
) -> ProfileConfiguration:
    """
    profile_configuration_from_yaml creates a ProfileConfiguration
    object from a parsed YAML file.
    """
    profile_config = ProfileConfiguration()
    profile_config.type = ProfileType(profile_config_yaml["type"])
    profile_config.userjs = (
        profile_config_yaml["userjs"] if "userjs" in profile_config_yaml else None
    )
    return profile_config


class ProfileInstantiation(Enum):
    """
    ProfileInstantiation describes different ways to handle
    instantiation of a profile.
    """

    SINGLE = "single"
    MULTIPLE = "multiple"


class Profile:
    """Profile describes a multifox profile."""

    configuration: ProfileConfiguration
    id: str
    instantiation: ProfileInstantiation
    name: str


def profile_from_yaml(
    profile_yaml,
) -> Profile:
    """
    profile_from_yaml creates a Profile object from a parsed YAML
    file.
    """
    profile = Profile()
    profile.configuration = profile_configuration_from_yaml(
        profile_yaml["configuration"]
    )
    profile.id = profile_yaml["id"]
    profile.instantiation = ProfileInstantiation(profile_yaml["instantiation"])
    profile.name = profile_yaml["name"]
    return profile


class Configuration:
    """Configuration holds the global multifox configuration."""

    profiles: List[Profile]


def configuration_from_yaml(
    config_yaml,
) -> Configuration:
    """
    configuration_from_yaml creates a Configuration object from a
    parsed YAML file.
    """
    config = Configuration()
    config.profiles = [profile_from_yaml(p) for p in config_yaml["profiles"]]
    return config


class Instance:
    """Instance holds information about a profile instance."""

    creation_time: datetime = datetime.now()
    id: str = ""
    profile_id: str = ""
    usage_pid: Optional[int] = None

    def to_yaml(self):
        """
        to_yaml returns a dictionary containing this object's data.

        The dictionary is serializable to YAML.
        """
        return {
            "creation_time": self.creation_time,
            "id": self.id,
            "profile_id": self.profile_id,
            "usage_pid": self.usage_pid,
        }


def instance_from_yaml(
    instance_yaml,
) -> Instance:
    """
    instance_from_yaml creates an Instance object from a parsed YAML
    file.
    """
    instance = Instance()
    instance.creation_time = instance_yaml["creation_time"]
    instance.id = instance_yaml["id"]
    instance.profile_id = instance_yaml["profile_id"]
    instance.usage_pid = (
        instance_yaml["usage_pid"] if "usage_pid" in instance_yaml else None
    )
    return instance


class BrokenProfileException(click.ClickException):
    """BrokenProfileException marks a broken profile."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken profile: {message}"

    def __str__(self):
        return self.message


class BrokenInstanceException(click.ClickException):
    """BrokenInstanceException marks a broken profile instance."""

    def __init__(self, message):
        super().__init__(message)
        self.message = f"Broken instance: {message}"

    def __str__(self):
        return self.message


def enum_synopsis(enum) -> str:
    """
    enum_synopsis returns a human-readably overview of an enum's
    values.
    """
    return "|".join([v.value for v in enum])


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
@click.option("--profile", "-p", nargs=1, help="Use the given profile")
@click.argument("args", nargs=-1)
def launch(profile, args):
    """Start a browser instance"""
    profile_name = profile
    if profile_name is None or profile_name == "":
        raise click.UsageError(
            "Selecting a profile dynamically is not implemented yet. `--profile` is required."
        )

    config = load_config()
    profile = find_profile_by_name(config.profiles, profile_name)
    if profile is None:
        raise click.UsageError(f'Profile "{profile_name}" does not exist')

    instance = find_best_instance_for_start(profile)

    if instance_in_use(instance):
        raise Exception(f"Instance is currently in use by process {instance.usage_pid}")

    instance.usage_pid = os.getpid()
    write_instance(instance)
    try:
        apply_config_to_instance(profile.configuration, instance)
        launch_browser(profile.configuration.type, instance, args)
    finally:
        instance.usage_pid = None
        write_instance(instance)


def load_config() -> Configuration:
    """load_config loads the global multifox configuration."""
    config_file = os.path.join(get_config_dir(), "config.yml")
    with open(config_file, "r", encoding="utf-8") as f:
        return configuration_from_yaml(yaml.load(f))


def find_profile_by_name(profiles: List[Profile], name: str) -> Optional[Profile]:
    """
    find_profile_by_name returns the profile from the given list of
    profiles whose name matches the given name.
    """
    for profile in profiles:
        if profile.name == name:
            return profile
    return None


def find_best_instance_for_start(profile: Profile) -> Instance:
    """
    find_best_instance_for_start returns the instance to use for the
    given profile when launching a browser.

    For profiles with single instantiation mode, this means return
    the only existing instance or create a new one if none exist.

    For profiles with multi instantiation mode, this means return an
    instance that's not in use or create a new one if all existing
    instances are in use. The oldest instance (by creation time) will
    be returned when using an existing instance. This encourages
    long-lived instances and generally comes closest to a "normal"
    browser usage which might be beneficial for avoiding breakage and
    (in the case of Tor Browser) anonymity.
    """

    instance_base_dir = get_instance_base_dir(profile.id)
    os.makedirs(instance_base_dir, mode=0o755, exist_ok=True)
    instance_dirs = os.listdir(instance_base_dir)
    if profile.instantiation == ProfileInstantiation.SINGLE:
        n_instances = len(instance_dirs)
        if n_instances == 1:
            return load_instance(os.path.join(instance_base_dir, instance_dirs[0]))
        if n_instances == 0:
            return create_instance(profile)
        raise BrokenProfileException(
            f'Profile "{profile.name}" is set to single instantiation mode but number of existing instances is {n_instances}'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
        )
    if profile.instantiation == ProfileInstantiation.MULTIPLE:
        oldest_free_instance = None
        for instance_dir in instance_dirs:
            instance = load_instance(os.path.join(instance_base_dir, instance_dir))
            if instance_in_use(instance):
                continue
            if (
                oldest_free_instance is None
                or instance.creation_time < oldest_free_instance.creation_time
            ):
                oldest_free_instance = instance
        if oldest_free_instance is None:
            return create_instance(profile)
        return oldest_free_instance
    raise BrokenProfileException(
        f'"instantiation" must be one of {enum_synopsis(ProfileInstantiation)} but is "{profile.instantiation.value}"'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
    )


def create_instance(profile: Profile) -> Instance:
    """
    create_instance initializes a new instance for the given profile.
    """
    instance = Instance()
    instance.id = uuid.uuid4().__str__()
    instance.profile_id = profile.id
    instance.creation_time = datetime.now()
    write_instance(instance)
    instance_dir = os.path.join(get_instance_base_dir(profile.id), instance.id)
    subprocess.run(
        [
            get_executable(profile.configuration.type),
            "--screenshot",
            "/dev/null",
            "about:blank",
        ],
        check=True,
        env=with_instance_home(instance_dir, os.environ),
    )
    return instance


def apply_config_to_instance(config: ProfileConfiguration, instance: Instance):
    """
    apply_config_to_instance applies the given profile configuration
    to the given instance.
    """
    if config.userjs is not None:
        src_userjs = os.path.join(get_config_dir(), config.userjs)
        dst_userjs = os.path.join(
            find_browser_profile_dir(
                config.type,
                os.path.join(get_instance_base_dir(instance.profile_id), instance.id),
            ),
            "user.js",
        )
        shutil.copyfile(src_userjs, dst_userjs)


def launch_browser(profile_type: ProfileType, instance: Instance, args: List[str]):
    """
    launch_browser launches the browser program for the given profile
    instance.
    """
    subprocess.run(
        [get_executable(profile_type)] + list(args),
        check=True,
        env=with_instance_home(
            os.path.join(get_instance_base_dir(instance.profile_id), instance.id),
            os.environ,
        ),
    )


def find_browser_profile_dir(profile_type: ProfileType, instance_dir: str) -> str:
    """
    find_browser_profile_dir returns a path to the actual browser
    profile for the given instance.

    profile_type must be set to the instance's profile type.
    """
    if profile_type == ProfileType.FIREFOX:
        firefox_dir = os.path.join(instance_dir, ".mozilla", "firefox")
        profile_dirs = [p for p in os.listdir(firefox_dir) if p.endswith(".default")]
        if len(profile_dirs) != 1:
            raise BrokenInstanceException(
                "Firefox profiles in instance directory != 1 but an instance should only ever contain one browser profile"  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
            )
        profile_dir = os.path.join(firefox_dir, profile_dirs[0])
        return profile_dir
    if profile_type == ProfileType.TOR_BROWSER:
        profile_dir = os.path.join(
            instance_dir,
            ".local",
            "share",
            "tor-browser",
            "TorBrowser",
            "Data",
            "Browser",
            "profile.default",
        )
        if not os.path.isdir(profile_dir):
            raise BrokenInstanceException(
                f'Instance does not contain a profile (no directory at "{profile_dir}")'
            )
        return profile_dir
    raise ValueError(f'"type" must be one of ({enum_synopsis(ProfileType)})')


def get_executable(profile_type: ProfileType) -> str:
    """
    get_executable returns the browser executable to use for the
    profile.
    """
    if profile_type == ProfileType.FIREFOX:
        return "firefox"
    if profile_type == ProfileType.TOR_BROWSER:
        return "tor-browser"
    raise ValueError(
        f'Unknown profile type "{profile_type.value}". Must be one of {enum_synopsis(ProfileType)}.'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
    )


def with_instance_home(instance_dir, env):
    """
    with_instance_home returns a copy of the given environment
    variables that causes browsers to create their profiles under the
    given path.
    """
    new_env = dict(env)
    new_env["HOME"] = instance_dir
    return new_env


def instance_in_use(instance: Instance) -> bool:
    """
    instance_in_use checks if the given instance is currently in use
    by a multifox process.
    """
    if instance.usage_pid is None:
        return False
    return check_pid(instance.usage_pid)


def load_instance(instance_dir: str) -> Instance:
    """
    load_instance loads instance information from the given instance
    directory.
    """
    instance_info_file = os.path.join(instance_dir, "instance.yml")
    with open(instance_info_file, "r", encoding="utf-8") as f:
        instance_yaml = yaml.load(f, Loader=yaml.CLoader)
        return instance_from_yaml(instance_yaml)


def write_instance(instance: Instance):
    """
    write_instance writes the given instance information to disk.
    """
    instance_dir = os.path.join(get_instance_base_dir(instance.profile_id), instance.id)
    instance_info_file = os.path.join(instance_dir, "instance.yml")
    os.makedirs(instance_dir, mode=0o755, exist_ok=True)
    with open(instance_info_file, "w", encoding="utf-8") as f:
        yaml.dump(instance.to_yaml(), f, Dumper=yaml.CDumper)


def get_instance_base_dir(profile_id: str) -> str:
    """
    get_instance_base_dir returns the directory for all instances of
    the given profile.
    """
    return os.path.join(get_state_dir(), "instances", profile_id)


def get_config_dir() -> str:
    """get_config_dir returns the global configuration directory."""
    config_dir = (
        os.environ["XDG_CONFIG_HOME"]
        if "XDG_CONFIG_HOME" in os.environ
        else os.path.join(os.environ["HOME"], ".config")
    )
    config_dir = os.path.join(config_dir, "multifox")
    return config_dir


def get_state_dir() -> str:
    """
    get_state_dir returns the global state directory.

    This is where state that can't be derived automatically (like
    caches could) is stored. It is used for example for profile
    instances.
    """
    state_dir = (
        os.environ["XDG_STATE_HOME"]
        if "XDG_STATE_HOME" in os.environ
        else os.path.join(os.environ["HOME"], ".local", "state")
    )
    state_dir = os.path.join(state_dir, "multifox")
    return state_dir


# Taken from https://stackoverflow.com/a/568285
def check_pid(pid: int) -> bool:
    """check_pid checks if a process with the given PID exists."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


if __name__ == "__main__":
    multifox()
