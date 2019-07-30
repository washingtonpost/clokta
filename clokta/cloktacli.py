'''
This is the entry-point to the cli application.
'''
import click

from clokta.role_assumer import RoleAssumer, Common


@click.command()
@click.version_option()
@click.option('--profile', '-p', required=True, help='Configuration profile')
@click.option('--verbose', '-v', is_flag=True, help='Output internal state for debugging')
@click.option('--instructions', '-i', is_flag=True, help='Output explicit steps on how to use generated keys')
@click.option('--quiet', '-q', is_flag=True, help='Silences all output except final export command. All prompts are on stderr. This facilitate commands like "eval $(clokta -p default)"')
def assume_role(profile, verbose=False, instructions=False, quiet=False):
    ''' Click point of entry '''
    configure_output_format(verbose, instructions, quiet)
    assumer = RoleAssumer(profile=profile)
    assumer.assume_role()

def configure_output_format(verbose, instructions, quiet):
    '''
    Reads the three output-related command line flags and determines desired output 
    '''
    if verbose:
        Common.set_output_format(Common.verbose_out)
    elif quiet:
        Common.set_output_format(Common.quiet_out)
    elif instructions:
        Common.set_output_format(Common.long_out)
    else:
        Common.set_output_format(Common.brief_out)
