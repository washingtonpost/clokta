''' ConfigGenerator class must be instantiated prior to use '''
import copy
import getpass
import json
import os

import click
import yaml

from cli.common import Common


class ConfigGenerator(object):
    ''' Loads or otherwise generates configuration information '''

    @classmethod
    def generate_configuration(cls, config_section, verbose=False):
        ''' Configuration file values override environment variables '''
        configuration = {
            'okta_username': '',
            'okta_password': '',
            'okta_org': '',
            'multifactor_preference': '',
            'okta_aws_app_url': '',
            'okta_aws_role_to_assume': '',
            'okta_idp_provider': ''
        }
        for key in configuration:
            if key.endswith('password'):
                configuration[key] = os.getenv(
                    key=key,
                    default=getpass.getpass(prompt="Enter a value for {}: ".format(key))
                )
            elif key == 'multifactor_preference':
                if key in config_section:
                    configuration[key] = config_section.get(key)
                else:
                    configuration[key] = ''
            else:
                if key in config_section and config_section[key] is not '':
                    configuration[key] = config_section[key]
                else:
                    configuration[key] = os.getenv(
                        key=key,
                        default=click.prompt('Enter a value for {}'.format(key), type=str)
                    )

        if verbose:
            copy_config = copy.deepcopy(configuration)
            for key in copy_config:
                if key.endswith('password'):
                    copy_config[key] = '<redacted>'
            msg = 'Configuration: {}'.format(
                json.dumps(obj=copy_config, indent=4)
            )
            Common.dump_verbose(message=msg)

        return configuration
