''' ConfigGenerator class must be instantiated prior to use '''
import copy
import getpass
import json
import os

import click

from clokta.common import Common


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
            'okta_aws_role_to_assume': ''
        }
        for key in configuration:
            if key.endswith('password'):
                # Passwords must always be gotten from the prompt
                configuration[key] = getpass.getpass(prompt="Enter a value for {}: ".format(key))
            elif key in ['multifactor_preference', 'okta_aws_role_to_assume']:
                # These settings may be specified in the config but if they are not
                # they have default behavior
                if key in config_section:
                    configuration[key] = config_section.get(key)
                else:
                    configuration[key] = ''
            else:
                if key in config_section and config_section[key] is not '':
                    configuration[key] = config_section[key]
                else:
                    Common.dump_err(
                        msg='Invalid configuration.  {} not defined in clokta.cfg.'.format(key),
                        error_code=6,
                        verbose=False)

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
