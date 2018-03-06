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
        configuration = {}
        for key in config_section:
            if key.endswith('password'):
                configuration[key] = os.getenv(
                    key,
                    getpass.getpass(prompt="Enter a value for {}:".format(key))
                )
            elif key == 'multifactor_preference':
                configuration[key] = config_section[key]
            else:
                configuration[key] = config_section[key] if config_section[key] \
                    else os.getenv(key, click.prompt('Enter a value for {}'.format(key), type=str))

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
