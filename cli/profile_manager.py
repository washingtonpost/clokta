''' ProfileManager class must be instantiated prior to use. '''
import configparser
import enum
import json
import os

from cli.common import Common
from cli.config_generator import ConfigGenerator


class OutputFormat(enum.Enum):
    ''' Enumeration for credentials output format codes '''
    ShellScript = 'SHELL'
    Profile = 'PROFILE'
    All = 'ALL'


class ProfileManager(object):
    ''' Supports profile file management '''

    def __init__(self, profile_name, config_location='~/.clokta/clokta.cfg', profiles_location='~/.aws/credentials', verbose=False):

        ''' Instance constructor '''
        self.profile_name = profile_name
        self.verbose = verbose
        self.profiles_location = os.path.expanduser(profiles_location)
        self.config_location = os.path.expanduser(config_location)

    def load_config(self):
        parser = configparser.ConfigParser()
        parser.read(self.config_location)

        if not parser['DEFAULT']:
            parser['DEFAULT'] = {
                'okta_username': '',
                'okta_password': '',
                'okta_org': '',
                'multifactor_preference': ''
            }

        if self.profile_name not in parser.sections():
            parser[self.profile_name] = {
                'okta_aws_app_url': '',
                'okta_aws_role_to_assume': '',
                'okta_idp_provider': ''
            }

        config_section = parser[self.profile_name]
        updated_config = ConfigGenerator.generate_configuration(
            config_section=config_section,
            verbose=self.verbose
        )
        return updated_config

    def apply_configuration(self, profile_configuration):
        ''' Save a named configuration '''
        parser = configparser.ConfigParser()
        parser.read(self.config_location)

        default_keys = [
            'okta_username',
            'okta_org',
            'multifactor_preference'
        ]
        for key in default_keys:
            parser['DEFAULT'][key] = profile_configuration[key]

        profile_keys = [
            'okta_aws_app_url',
            'okta_aws_role_to_assume',
            'okta_idp_provider'
        ]
        for key in profile_keys:
            parser[self.profile_name][key] = profile_configuration[key]

        if self.verbose:
            Common.dump_verbose(
                message='Re-writing configuration file {}'.format(self.config_location)
            )
        self.__write_config(
            path_to_file=self.config_location,
            parser=parser
        )

    def apply_credentials(self, credentials):
        ''' Save a set of temporary credentials '''
        if self.verbose:
            msg = json.dumps(obj=credentials, default=Common.json_serial, indent=4)
            Common.dump_verbose(message=msg)

        parser = configparser.ConfigParser()
        parser.read(self.profiles_location)

        if self.profile_name not in parser.sections():
            if self.verbose:
                Common.dump_verbose(
                    message='Adding profile section {}'.format(self.profile_name)
                )
            parser.add_section(self.profile_name)

        creds = credentials['Credentials']
        parser[self.profile_name]['AWS_ACCESS_KEY_ID'] = creds['AccessKeyId']
        parser[self.profile_name]['AWS_SECRET_ACCESS_KEY'] = creds['SecretAccessKey']
        if 'SessionToken' in creds:
            parser[self.profile_name]['AWS_SESSION_TOKEN'] = creds['SessionToken']

        if self.verbose:
            Common.dump_verbose(
                message='Re-writing credentials file {}'.format(self.profiles_location)
            )

        self.__write_config(
            path_to_file=self.profiles_location,
            parser=parser
        )

    def __write_config(self, path_to_file, parser):
        ''' Write config to file '''
        self.__backup_file(path_to_file=path_to_file)

        if not os.path.exists(os.path.dirname(path_to_file)):
            os.makedirs(os.path.dirname(path_to_file))

        with open(path_to_file, 'w') as file:
            parser.write(file)

    def __backup_file(self, path_to_file):
        ''' Back up config '''
        backup_location = os.path.expanduser(
            '{}.bak'.format(
                path_to_file
            )
        )
        if os.path.isfile(path=path_to_file):
            with open(path_to_file, 'r') as file:
                contents = file.read()

            with open(backup_location, 'w') as bak_file:
                bak_file.write(contents)

    def write_sourceable_file(self, credentials):
        '''
        Generates a shell script to source in order to apply credentials to the shell environment.
        '''
        creds = credentials['Credentials']
        output_file_name = '{dir}/{profile}.sh'.format(
            dir=os.path.dirname(self.config_location),
            profile=self.profile_name
        )
        lines = [
            'export AWS_ACCESS_KEY_ID={}\n'.format(creds['AccessKeyId']),
            'export AWS_SECRET_ACCESS_KEY={}\n'.format(creds['SecretAccessKey'])
        ]
        if 'SessionToken' in creds:
            lines.append('export AWS_SESSION_TOKEN={}\n'.format(creds['SessionToken']))

        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)
        Common.echo(
            message='AWS keys saved to {loc}. To use, `source {loc}`'.format(
                loc=output_file_name
            )
        )

    def write_dockerenv_file(self, credentials):
        '''
        Generates a Docker .env file that can be used with docker compose to inject into the environment.
        '''
        creds = credentials['Credentials']
        output_file_name = '{dir}/{profile}.env'.format(
            dir=os.path.dirname(self.config_location),
            profile=self.profile_name
        )
        lines = [
            'AWS_ACCESS_KEY_ID={}\n'.format(creds['AccessKeyId']),
            'AWS_SECRET_ACCESS_KEY={}\n'.format(creds['SecretAccessKey'])
        ]
        if 'SessionToken' in creds:
            lines.append('AWS_SESSION_TOKEN={}\n'.format(creds['SessionToken']))

        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)
        Common.echo(
            message='AWS keys saved to {loc} for use with docker compose'.format(
                loc=output_file_name
            )
        )
