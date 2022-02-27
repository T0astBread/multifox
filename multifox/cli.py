"""
cli contains declarations and implementations of multifox commands.
"""

import os
import sys

import click

import multifox
from multifox import gui

# HACK: `argv[0]`` gets mangled by wrappers when packaging for Nix,
# so set it explicitly here.
sys.argv[0] = "multifox"


@click.group(add_help_option=False, invoke_without_command=True)
@click.help_option("--help", "-h", help="Show this message and exit")
@click.pass_context
def cli(ctx: click.Context):
    """
    Launch and manage mutliple instances of Firefox and the Tor
    Browser.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(launch)


@cli.command(add_help_option=False)
@click.help_option("--help", "-h", help="Show this message and exit")
@click.option("--profile", "-p", nargs=1, help="Use the given profile")
@click.argument("args", nargs=-1)
def launch(profile, args):
    """Start a browser instance"""
    config = multifox.load_config()

    profile_name = profile
    if profile_name is None or profile_name == "":
        profile_name = gui.select_profile(config)
        if profile_name is None:
            raise click.UsageError("No profile selected")

    profile = multifox.find_profile_by_name(config.profiles, profile_name)
    if profile is None:
        raise click.UsageError(f'Profile "{profile_name}" does not exist')

    instance = multifox.find_best_instance_for_start(profile)

    if multifox.instance_in_use(instance):
        raise Exception(f"Instance is currently in use by process {instance.usage_pid}")

    instance.usage_pid = os.getpid()
    multifox.write_instance(instance)
    try:
        multifox.apply_config_to_instance(profile.configuration, instance)
        multifox.launch_browser(profile.configuration.type, instance, args)
    finally:
        instance.usage_pid = None
        multifox.write_instance(instance)
