''' ConfigLoader class must be instantiated prior to use '''
import copy
import getpass
import os

import click
import yaml

from six.moves import input


class ConfigLoader(object):
    ''' Loads or otherwise generates configuration information '''

    @classmethod
    def load_configuration(cls, config_path, verbose=False):
        ''' Configuration file values override environment variables '''
        cfg = {}
        configuration = {}
        if config_path:
            try:
                with open(config_path, 'r') as config_file:
                    contents = config_file.read()
                    cfg = yaml.load(contents, Loader=yaml.SafeLoader)
            except OSError as oserr:
                msg = 'Error related to your configuration file: {}'.format(oserr)
                logging.exception(msg) if verbose else print(msg)
                sys.exit(1)
            except Exception as err:
                msg = 'Unexpected error: {}'.format(err)
                logging.exception(msg) if verbose else print(msg)
                sys.exit(1)

        for key in [
                'OKTA_USERNAME',
                'OKTA_PASSWORD',
                'OKTA_ORG',
                'OKTA_AWS_APP_URL',
                'OKTA_AWS_ROLE_TO_ASSUME',
                'OKTA_IDP_PROVIDER',
                'MULTIFACTOR_PREFERENCE'
        ]:
            if key.endswith('PASSWORD'):
                configuration[key] = os.getenv(
                    key,
                    getpass.getpass(prompt="Enter a value for {}:".format(key))
                )
            elif key == 'MULTIFACTOR_PREFERENCE':
                configuration[key] = cfg.get(key)
            else:
                configuration[key] = cfg.get(key) if cfg.get(key) \
                    else os.getenv(key, input("Enter a value for {}:".format(key)))

        if verbose:
            copy_config = copy.deepcopy(configuration)
            copy_config['OKTA_PASSWORD'] = '<redacted>'
            click.echo('Configuration:')
            click.echo(copy_config)

        return configuration
