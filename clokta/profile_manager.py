''' ProfileManager class must be instantiated prior to use. '''
import click
import configparser
import enum
import json
import os

from clokta.common import Common
from clokta.config_generator import ConfigGenerator


class OutputFormat(enum.Enum):
    ''' Enumeration for credentials output format codes '''
    ShellScript = 'SHELL'
    Profile = 'PROFILE'
    All = 'ALL'


class ProfileManager(object):
    ''' Supports profile file management '''

    def __init__(
        self,
        profile_name,
        config_location='~/.clokta/clokta.cfg',
        profiles_location='~/.aws/credentials',
        verbose=False
    ):
        ''' Instance constructor '''
        self.profile_name = profile_name
        self.verbose = verbose
        self.profiles_location = os.path.expanduser(profiles_location)
        self.short_config_location = config_location
        self.config_location = os.path.expanduser(config_location)

    def initialize_configuration(self):
        ''' Generate and load config file section '''
        parser = configparser.ConfigParser()
        parser.read(self.config_location)

        if not parser['DEFAULT']:
            parser['DEFAULT'] = {
                'okta_org': ''
            }

        if self.profile_name not in parser.sections():
            msg = 'No profile "{}" in clokta.cfg, but enter the information and clokta will create a profile.\nCopy the link from the Okta App'
            app_url = click.prompt(msg.format(self.profile_name), type=str).strip()
            if not app_url.startswith("https://") or not app_url.endswith("?fromHome=true"):
                Common.dump_err("Invalid App URL.  URL usually of the form https://xxxxxxxx.okta.com/.../272?fromHome=true", 6, False)
            else:
                app_url = app_url[:-len("?fromHome=true")]
            parser[self.profile_name] = {
                'okta_aws_app_url': app_url
            }

        config_section = parser[self.profile_name]
        updated_config = ConfigGenerator.generate_configuration(
            config_section=config_section,
            verbose=self.verbose
        )
        self.__write_config(
            path_to_file=self.config_location,
            parser=parser
        )
        return updated_config

    def update_configuration(self, profile_configuration):
        ''' Update a config file section '''
        parser = configparser.ConfigParser()
        parser.read(self.config_location)

        default_keys = [field['name'] for field in ConfigGenerator.config_fields if 'save_to' in field and field['save_to']=='default']
        for key in default_keys:
            parser['DEFAULT'][key] = profile_configuration.get(key)

        profile_keys = [field['name'] for field in ConfigGenerator.config_fields if 'save_to' in field and field['save_to']=='profile']
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

    def prompt_for(self, field_name):
        return ConfigGenerator.prompt_for(field_name)

    def apply_credentials(self, credentials, echo_message=False):
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

        if 'AWS_SESSION_TOKEN' in parser[self.profile_name]:
            del parser[self.profile_name]['AWS_SESSION_TOKEN']

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
            'export AWS_PROFILE={}\n'.format(self.profile_name),
            'export AWS_ACCESS_KEY_ID={}\n'.format(creds['AccessKeyId']),
            'export AWS_SECRET_ACCESS_KEY={}\n'.format(creds['SecretAccessKey'])
        ]
        if 'SessionToken' in creds:
            lines.append('export AWS_SESSION_TOKEN={}\n'.format(creds['SessionToken']))
        else:
            lines.append('unset AWS_SESSION_TOKEN')

        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)

        short_output_file_name = '{dir}/{profile}.sh'.format(
            dir=os.path.dirname(self.short_config_location),
            profile=self.profile_name
        )
        return short_output_file_name

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
            'AWS_PROFILE={}\n'.format(self.profile_name),
            'AWS_ACCESS_KEY_ID={}\n'.format(creds['AccessKeyId']),
            'AWS_SECRET_ACCESS_KEY={}\n'.format(creds['SecretAccessKey'])
        ]
        if 'SessionToken' in creds:
            lines.append('AWS_SESSION_TOKEN={}\n'.format(creds['SessionToken']))

        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)

        short_output_file_name = '{dir}/{profile}.env'.format(
            dir=os.path.dirname(self.short_config_location),
            profile=self.profile_name
        )
        return short_output_file_name
