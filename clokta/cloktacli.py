"""
This is the entry-point to the cli application.
"""
import os

import click

from clokta.clokta_configuration import CloktaConfiguration
from clokta.role_assumer import RoleAssumer, Common


@click.command()
@click.version_option()
@click.option('--profile', '-p', help='Configuration profile.  Required unless specified by AWS_PROFILE')
@click.option('--inline-help', '-i', is_flag=True,
              help='Output explicit steps on how to use generated keys and override defaults')
@click.option('--no-default-role', is_flag=True, help='Lets you choose a different role than your default')
@click.option('--quiet', '-q', is_flag=True,
              help='Silences all output except final export command. All prompts are on stderr. ' +
                   'This facilitate commands like "eval $(clokta -p default)"')
@click.option('--verbose', '-v', is_flag=True, help='Output internal state for debugging')
@click.option('--list-accounts',  is_flag=True,
              help='List all accounts, profile and account number, configured in clokta')
def assume_role(profile, inline_help=False, no_default_role=False, quiet=False, verbose=False, list_accounts=False):
    """ Click point of entry """

    if list_accounts:
        CloktaConfiguration.dump_account_numbers('~/.clokta/clokta.cfg')
        exit(0)

    if not profile:
        profile = get_profile_from_env()
        if not profile:
            with click.Context(assume_role) as ctx:
                click.echo(assume_role.get_help(ctx))
                exit(0)

    configure_output_format(verbose, inline_help, quiet)
    assumer = RoleAssumer(profile=profile)
    assumer.assume_role(reset_default_role=no_default_role)


def configure_output_format(verbose, inline_help, quiet):
    """
    Reads the three output-related command line flags and determines desired output 
    """
    if verbose:
        Common.set_output_format(Common.debugging_out)
    elif quiet:
        Common.set_output_format(Common.quiet_out)
    elif inline_help:
        Common.set_output_format(Common.long_out)
    else:
        Common.set_output_format(Common.brief_out)


def get_profile_from_env():
    """
    Look up the AWS_PROFILE variable and return it
    :return: value of AWS_PROFILE, or None if not defined
    :rtype: stre
    """
    from_env = os.getenv(key='AWS_PROFILE')
    if from_env:
        Common.echo("Using profile '{}' from AWS_PROFILE".format(from_env))
    return from_env
