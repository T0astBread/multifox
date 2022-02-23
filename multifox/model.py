"""
model contains Python classes and associated functions for handling
program data in a structured way.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional


class ProfileType(Enum):
    """ProfileType marks what program a profile is for."""

    FIREFOX = "firefox"
    TOR_BROWSER = "tor-browser"


class ProfileConfiguration:
    """
    ProfileConfiguration describes settings and customizations of a
    browser profile.
    """

    extensions: Optional[List[str]]
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
    profile_config.extensions = (
        profile_config_yaml["extensions"]
        if "extensions" in profile_config_yaml
        else None
    )
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
    installed_extensions: List[str] = list()
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
            "installed_extensions": self.installed_extensions,
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
    instance.installed_extensions = instance_yaml["installed_extensions"]
    instance.profile_id = instance_yaml["profile_id"]
    instance.usage_pid = (
        instance_yaml["usage_pid"] if "usage_pid" in instance_yaml else None
    )
    return instance
