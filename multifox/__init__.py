"""
multifox helps you launch and manage multiple instances of Firefox
and the Tor Browser.

This module contains general functions and helpers.
"""

import json
import os
import shutil
import subprocess  # nosec  # It's okay to start processes.
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

import click
import yaml

from . import error, model
from .cli import cli


def enum_synopsis(enum) -> str:
    """
    enum_synopsis returns a human-readably overview of an enum's
    values.
    """
    return "|".join([v.value for v in enum])


def load_config() -> model.Configuration:
    """load_config loads the global multifox configuration."""
    config_file = os.path.join(get_config_dir(), "config.yml")
    with open(config_file, "r", encoding="utf-8") as f:
        return model.configuration_from_yaml(yaml.safe_load(f))


def find_profile_by_name(
    profiles: List[model.Profile], name: str
) -> Optional[model.Profile]:
    """
    find_profile_by_name returns the profile from the given list of
    profiles whose name matches the given name.
    """
    for profile in profiles:
        if profile.name == name:
            return profile
    return None


def find_best_instance_for_start(profile: model.Profile) -> model.Instance:
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
    if profile.instantiation == model.ProfileInstantiation.SINGLE:
        n_instances = len(instance_dirs)
        if n_instances == 1:
            return load_instance(os.path.join(instance_base_dir, instance_dirs[0]))
        if n_instances == 0:
            return create_instance(profile)
        raise error.BrokenProfileException(
            f'Profile "{profile.name}" is set to single instantiation mode but number of existing instances is {n_instances}'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
        )
    if profile.instantiation == model.ProfileInstantiation.MULTIPLE:
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
    raise error.BrokenProfileException(
        f'"instantiation" must be one of {enum_synopsis(model.ProfileInstantiation)} but is "{profile.instantiation.value}"'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
    )


def create_instance(profile: model.Profile) -> model.Instance:
    """
    create_instance initializes a new instance for the given profile.
    """
    instance = model.Instance()
    instance.id = uuid.uuid4().__str__()
    instance.profile_id = profile.id
    instance.creation_time = datetime.now()
    write_instance(instance)
    instance_dir = os.path.join(get_instance_base_dir(profile.id), instance.id)
    # There are no untrusted user inputs in this subprocess call.
    subprocess.run(  # nosec
        get_bubblewrap_cmd_line(profile.configuration.type, instance_dir)
        + [
            b"--screenshot",
            b"/dev/null",
            b"about:blank",
        ],
        check=True,
        env=os.environ,
    )
    return instance


def apply_config_to_instance(
    config: model.ProfileConfiguration, instance: model.Instance
):
    """
    apply_config_to_instance applies the given profile configuration
    to the given instance.
    """
    update_userjs(config, instance)
    install_extensions(config, instance)


def update_userjs(config: model.ProfileConfiguration, instance: model.Instance):
    """
    update_userjs updates an instance's user.js file from the file
    specified in the profile configuration.
    """
    userjs_in_instance = os.path.join(
        find_browser_profile_dir(
            config.type,
            os.path.join(get_instance_base_dir(instance.profile_id), instance.id),
        ),
        "user.js",
    )
    if config.userjs is None:
        if os.path.isfile(userjs_in_instance):
            os.remove(userjs_in_instance)
    else:
        src_userjs = os.path.join(get_config_dir(), config.userjs)
        shutil.copyfile(src_userjs, userjs_in_instance)

    # Set preference to enable unattended extension installation from extensions folder.
    if config.extensions is not None and len(config.extensions) > 0:
        with open(userjs_in_instance, "a", encoding="utf-8") as f:
            f.write('user_pref("extensions.autoDisableScopes", 14);\n')


def install_extensions(config: model.ProfileConfiguration, instance: model.Instance):
    """
    install_extensions installs and removes extensions in the profile
    to match the given configuration.
    """
    config_path = get_config_dir()
    instance_dir = os.path.join(
        get_instance_base_dir(instance.profile_id),
        instance.id,
    )
    browser_profile_dir = find_browser_profile_dir(config.type, instance_dir)
    extensions_base_path = os.path.join(browser_profile_dir, "extensions")

    # Remove all installed extensions by default.
    to_remove = set(instance.installed_extensions)
    to_install = set()

    # Go over wanted extensions, keep the ones we already have and install the missing ones.
    if config.extensions is not None:
        for extension_file_path in config.extensions:
            extension_file_name = os.path.basename(extension_file_path)
            if extension_file_name in to_remove:
                # The extension is already installed and does not need to be removed.
                to_remove.remove(extension_file_name)
            else:
                # The extension is not already installed and needs to be installed.
                to_install.add(extension_file_path)

    # Read extension-preferences.json
    extension_preferences = None
    extension_preferences_path = os.path.join(
        browser_profile_dir, "extension-preferences.json"
    )
    with open(extension_preferences_path, "r", encoding="utf-8") as ext_pref_file:
        extension_preferences = json.load(ext_pref_file)

    # Actually apply the remove list.
    for extension_file_name in to_remove:
        extension_id = extension_id_from_file_path(extension_file_name)

        # Delete from extensions dir.
        extension_in_instance = os.path.join(extensions_base_path, extension_file_name)
        if os.path.isfile(
            extension_in_instance
        ):  # Handle broken instances that can still be saved by ignoring already missing files.
            os.remove(extension_in_instance)

        # Delete from extension-prefereces file.
        del extension_preferences[extension_id]

    # Actually apply the install list.
    for rel_extension_file_path in to_install:
        extension_file_path = os.path.join(config_path, rel_extension_file_path)
        extension_file_name = os.path.basename(extension_file_path)
        extension_id = extension_id_from_file_path(extension_file_name)

        # Copy to extensions dir.
        extension_in_instance = os.path.join(extensions_base_path, extension_file_name)
        os.makedirs(extensions_base_path, mode=0o755, exist_ok=True)
        shutil.copyfile(
            extension_file_path, extension_in_instance, follow_symlinks=True
        )

        # Add to extension-preferences file.
        extension_preferences[extension_id] = {
            "permissions": ["internal:privateBrowsingAllowed"],
            "origins": [],
        }

    # Write out extension-preferences.json.
    with open(extension_preferences_path, "w", encoding="utf-8") as ext_pref_file:
        json.dump(extension_preferences, ext_pref_file)

    # Update instance info.
    instance.installed_extensions = (
        [os.path.basename(p) for p in config.extensions]
        if config.extensions is not None
        else []
    )
    write_instance(instance)

    # Start the browser once to finish installation or removal of addons.
    if len(to_remove) + len(to_install) > 0:
        # Start zenity to display a progress bar.

        # We trust that the PATH variable has not been manipulated by
        # a malicious actor here.
        #
        # Additionally, no outside input is passed to this process.
        zenity = subprocess.Popen(  # nosec
            [
                "zenity",
                "--progress",
                "--no-cancel",
                "--title",
                "Installing extensions",
                "--width",
                "400",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ,
        )

        # Start the browser to do some extension installation
        # activation magic.

        # There is no untrusted input in this subprocess invocation.
        proc = subprocess.Popen(  # nosec
            get_bubblewrap_cmd_line(
                config.type,
                instance_dir,
                allow_net=False,
                extra_bwrap_args=[b"--die-with-parent"],
            )
            + [b"--headless"],
        )

        # HACK: Wait for ten seconds so that the browser can finish
        # initializing our new extensions.
        #
        # I'm not sure what the browser is actually doing here but
        # shorter timeouts (tried with five seconds) don't work.
        #
        # It would be nice to have a more stable installation method,
        # maybe via Selenium? (Apparently Selenium can install
        # extensions.)
        for i in range(1, 101):
            time.sleep(0.1)
            # Update the zenity progress bar.
            zenity_stdin = zenity.stdin
            if zenity_stdin is not None:
                zenity_stdin.write(f"{i}\n".encode("utf-8"))
                zenity_stdin.flush()

        # Stop and wait for the browser and zenity.
        zenity.terminate()
        proc.terminate()
        proc.wait()


def extension_id_from_file_path(extension_file_path: str) -> str:
    """
    extension_id_from_file_path returns the ID of an extension at the
    given file path.

    The extension file must be named "<extension-id>.xpi".
    """
    return os.path.basename(extension_file_path).rstrip(".xpi")


def launch_browser(
    profile_type: model.ProfileType, instance: model.Instance, args: List[bytes]
):
    """
    launch_browser launches the browser program for the given profile
    instance.
    """
    instance_dir = os.path.join(get_instance_base_dir(instance.profile_id), instance.id)
    # args can be used to pass arbitrary arguments to the browser but it is assumed to be trusted.
    subprocess.run(  # nosec
        get_bubblewrap_cmd_line(profile_type, instance_dir) + list(args),
        check=True,
        env=os.environ,
    )


def find_browser_profile_dir(profile_type: model.ProfileType, instance_dir: str) -> str:
    """
    find_browser_profile_dir returns a path to the actual browser
    profile for the given instance.

    profile_type must be set to the instance's profile type.
    """
    if profile_type == model.ProfileType.FIREFOX:
        firefox_dir = os.path.join(instance_dir, ".mozilla", "firefox")
    if profile_type == model.ProfileType.LIBREWOLF:
        firefox_dir = os.path.join(instance_dir, ".librewolf")
    if profile_type == model.ProfileType.FIREFOX or profile_type == model.ProfileType.LIBREWOLF:
        profile_dirs = [p for p in os.listdir(firefox_dir) if p.endswith(".default")]
        if len(profile_dirs) != 1:
            raise error.BrokenInstanceException(
                "Browser profiles in instance directory != 1 but an instance should only ever contain one browser profile"  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
            )
        profile_dir = os.path.join(firefox_dir, profile_dirs[0])
        return profile_dir
    if profile_type == model.ProfileType.TOR_BROWSER:
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
            raise error.BrokenInstanceException(
                f'Instance does not contain a profile (no directory at "{profile_dir}")'
            )
        return profile_dir
    raise ValueError(f'"type" must be one of ({enum_synopsis(model.ProfileType)})')


def get_bubblewrap_cmd_line(
    profile_type: model.ProfileType,
    instance_dir: str,
    allow_net=True,
    extra_bwrap_args: Optional[List[bytes]] = None,
) -> List[bytes]:
    """
    get_bubblewrap_cmd_line returns the full command line to use for
    running the instance's browser in a sandbox on the instance.

    Additional arguments can be appended at the end.
    """
    executable = os.path.realpath(
        # There is no untrusted input in this subprocess invocation.
        subprocess.check_output(  # nosec
            ["which", get_executable(profile_type)]
        ).rstrip(b"\n")
    )

    extra_store_paths = set()
    for path in ["/etc/fonts", "/etc/ssl", "/etc/static/ssl"]:
        for dirpath, dirnames, filenames in os.walk(path):
            for dirname in dirnames + filenames:
                realpath = os.path.realpath(os.path.join(dirpath, dirname))
                if realpath.startswith("/nix/store/"):
                    extra_store_paths.add(realpath.encode("utf-8"))

    store_paths = (
        # It is assumed that the location of the browser executable
        # does not constitute harmful input for this subprocess call.
        subprocess.check_output(  # nosec
            [b"nix-store", b"--query", b"--requisites", executable]
            + list(extra_store_paths)
        )
        .rstrip(b"\n")
        .splitlines()
    )

    cmd_line = [b"bwrap"]
    for store_path in store_paths:
        cmd_line.append(b"--ro-bind")
        cmd_line.append(store_path)
        cmd_line.append(store_path)

    # NOTE: We can't bind D-Bus since Firefox "merges" profiles with
    # D-Bus enabled.

    pulseaudio_socket_path = f'{os.environ["XDG_RUNTIME_DIR"]}/pulse'

    # While X is not great security-wise, this is not an insecure
    # usage of a temporary file/directory like Bandit claims.
    x_socket_path = "/tmp/.X11-unix/"  # nosec

    for arg in [
        "--unshare-all",
        "--setenv",
        "HOME",
        "/home/user",
        "--setenv",
        "USER",
        "user",
        "--ro-bind",
        "/etc/fonts",
        "/etc/fonts",
        "--ro-bind",
        "/etc/ssl",
        "/etc/ssl",
        "--ro-bind",
        "/etc/static/ssl",
        "/etc/static/ssl",
        "--bind",
        instance_dir,
        "/home/user",
        "--setenv",
        "DISPLAY",
        os.environ["DISPLAY"],
        "--bind",
        x_socket_path,
        x_socket_path,
        "--bind",
        pulseaudio_socket_path,
        pulseaudio_socket_path,
        "--dev",
        "/dev",
        "--proc",
        "/proc",
    ]:
        cmd_line.append(arg.encode(encoding="utf-8"))

    if allow_net:
        cmd_line.append(b"--share-net")

    if extra_bwrap_args is not None:
        for extra_arg in extra_bwrap_args:
            cmd_line.append(extra_arg)

    cmd_line.append(b"--")
    cmd_line.append(executable)

    return cmd_line


def get_executable(profile_type: model.ProfileType) -> str:
    """
    get_executable returns the browser executable to use for the
    profile.
    """
    if profile_type == model.ProfileType.FIREFOX:
        return "firefox"
    if profile_type == model.ProfileType.LIBREWOLF:
        return "librewolf"
    if profile_type == model.ProfileType.TOR_BROWSER:
        return "tor-browser"
    raise ValueError(
        f'Unknown profile type "{profile_type.value}". Must be one of {enum_synopsis(model.ProfileType)}.'  # pylint: disable=line-too-long  # This is a string, what do you expect me to do?
    )


def instance_in_use(instance: model.Instance) -> bool:
    """
    instance_in_use checks if the given instance is currently in use
    by a multifox process.
    """
    if instance.usage_pid is None:
        return False
    return check_pid(instance.usage_pid)


def load_instance(instance_dir: str) -> model.Instance:
    """
    load_instance loads instance information from the given instance
    directory.
    """
    instance_info_file = os.path.join(instance_dir, "instance.yml")
    with open(instance_info_file, "r", encoding="utf-8") as f:
        instance_yaml = yaml.safe_load(f)
        return model.instance_from_yaml(instance_yaml)


def write_instance(instance: model.Instance):
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
