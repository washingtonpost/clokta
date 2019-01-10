'''
This is the entry-point to the cli application.
'''
import click

from clokta.role_assumer import RoleAssumer


@click.command()
@click.version_option()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed')
@click.option('--profile', '-p', required=True, help='Configuration profile')
def assume_role(profile, verbose=False):
    ''' Click point of entry '''
    assumer = RoleAssumer(profile=profile, verbose=verbose)
    assumer.assume_role()
