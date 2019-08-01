import click
import configparser
import enum
import json
import os

from clokta.common import Common
from clokta.config_generator import ConfigGenerator
from clokta.factor_chooser import FactorChooser
from clokta.role_chooser import RoleChooser


class OutputFormat(enum.Enum):
    """ Enumeration for credentials output format codes """
    ShellScript = 'SHELL'
    Profile = 'PROFILE'
    All = 'ALL'


class CloktaConfiguration(object):
    """
    This handles collecting and storing the configuration paramaters needed to clokta into a system
    It encapsulates reading and storing values from the clokta.cfg file, reading and storing passwords from
    keyring, and prompting the user for values.
    """

    def __init__(
        self,
        profile_name,
        clokta_config_file,
        profiles_location='~/.aws/credentials'
    ):
        """ Instance constructor """
        self.profile_name = profile_name
        self.profiles_location = os.path.expanduser(profiles_location)
        self.clokta_config_file = os.path.expanduser(clokta_config_file)
        self.config_parameters = self.__initialize_configuration()

    def get(self, parameter_name):
        """
        Get the current value of a configuration parameter
        :param parameter_name: the name of the parameter
        :type parameter_name: str
        :return: the value of the parameter or None if not present
        """
        return self.config_parameters.get(parameter_name)

    def get_parameters(self):
        """
        :return: all the parameters
        :rtype: dict[str, str]
        """
        return self.config_parameters

    def __initialize_configuration(self):
        """
        Generate and load config file section
        :return: the parameter list
        :rtype: dict
        """
        clokta_cfg_file = configparser.ConfigParser()
        clokta_cfg_file.read(self.clokta_config_file)

        if not clokta_cfg_file['DEFAULT']:
            clokta_cfg_file['DEFAULT'] = {
                'okta_org': ''
            }

        if self.profile_name not in clokta_cfg_file.sections():
            msg = 'No profile "{}" in clokta.cfg, but enter the information and clokta will create a profile.\n' + \
                'Copy the link from the Okta App'
            app_url = click.prompt(text=msg.format(self.profile_name), type=str, err=Common.to_std_error()).strip()
            if not app_url.startswith("https://") or not app_url.endswith("?fromHome=true"):
                Common.dump_err(
                    "Invalid App URL.  URL usually of the form https://xxxxxxxx.okta.com/.../272?fromHome=true", 6
                )
            else:
                app_url = app_url[:-len("?fromHome=true")]
            clokta_cfg_file[self.profile_name] = {
                'okta_aws_app_url': app_url
            }

        config_section = clokta_cfg_file[self.profile_name]
        updated_config = ConfigGenerator.generate_configuration(
            config_section=config_section
        )
        self.__write_config(
            path_to_file=self.clokta_config_file,
            parser=clokta_cfg_file
        )
        return updated_config

    def update_configuration(self):
        profile_configuration = self.config_parameters
        ''' Update a config file section '''
        parser = configparser.ConfigParser()
        parser.read(self.clokta_config_file)

        default_keys = [field['name'] for field in ConfigGenerator.config_fields
                        if 'save_to' in field and field['save_to'] == 'default']
        for key in default_keys:
            parser['DEFAULT'][key] = profile_configuration.get(key)

        profile_keys = [field['name'] for field in ConfigGenerator.config_fields
                        if 'save_to' in field and field['save_to'] == 'profile']
        for key in profile_keys:
            parser[self.profile_name][key] = profile_configuration[key]

        if Common.is_debug():
            Common.dump_out(
                message='Re-writing configuration file {}'.format(self.clokta_config_file)
            )
        self.__write_config(
            path_to_file=self.clokta_config_file,
            parser=parser
        )

    def prompt_for(self, field_name):
        return ConfigGenerator.prompt_for(field_name)

    def apply_credentials(self, credentials):
        """ Save a set of temporary credentials """
        if Common.is_debug():
            msg = json.dumps(obj=credentials, default=Common.json_serial, indent=4)
            Common.dump_out(message=msg)

        parser = configparser.ConfigParser()
        parser.read(self.profiles_location)

        if self.profile_name not in parser.sections():
            if Common.is_debug():
                Common.dump_out(
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

        if Common.is_debug():
            Common.dump_out(
                message='Re-writing credentials file {}'.format(self.profiles_location)
            )

        self.__write_config(
            path_to_file=self.profiles_location,
            parser=parser
        )

    def __write_config(self, path_to_file, parser):
        """ Write config to file """
        self.__backup_file(path_to_file=path_to_file)

        if not os.path.exists(os.path.dirname(path_to_file)):
            os.makedirs(os.path.dirname(path_to_file))

        with open(path_to_file, 'w') as file:
            parser.write(file)

    def __backup_file(self, path_to_file):
        """ Back up config """
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

    def determine_mfa_mechanism(self, mfas):
        """
        Determine which of the passed in MFA mechanisms to use.  This may be specified
        by the configuration's 'multifactor_preference' if not prompt the user and put
        in the configuration
        :param mfas: possible mechanisms to use for MFA
        :type mfas: List[dict]
        :return: the chosen MFA mechanism to use
        :rtype: dict
        """

        factor_preference = self.get('multifactor_preference')
        fact_chooser = FactorChooser(
            factors=mfas,
            factor_preference=factor_preference
        )

        # Is there only one legitimate MFA option available?
        if len(mfas) == 1:
            factor = fact_chooser.verify_only_factor(factor=mfas[0])
            if factor:
                return factor

        # Has the user pre-selected a legitimate factor?
        if factor_preference:
            factor = fact_chooser.verify_preferred_factor()
            if factor:
                return factor

        return fact_chooser.choose_supported_factor()

    def determine_role(self, possible_roles):
        """
        Determine which of several possible roles to assume by looking first in the config for a default role,
        and second by prompting the user.
        :param possible_roles: list of possible roles to assume
        :type possible_roles: str
        :return: the role chosen
        :rtype: AwsRole
        """
        role_chooser = RoleChooser(
            possible_roles=possible_roles,
            role_preference=self.get('okta_aws_role_to_assume')
        )
        chosen_role = role_chooser.choose_role()
        self.config_parameters['okta_aws_role_to_assume'] = chosen_role.role_arn
        return chosen_role

    def determine_password(self):
        if 'okta_password' not in self.config_parameters or not self.config_parameters['okta_password']:
            self.config_parameters['okta_password'] = self.prompt_for('okta_password')


    def determine_okta_onetimepassword(self):
        """
        Get the one time password, which may be in one password or
        may need to be prompted for
        """

        otp_value = None
        if self.get('okta_onetimepassword_secret'):
            try:
                # noinspection PyUnresolvedReferences
                import onetimepass as otp
            except ImportError:
                msg = 'okta_onetimepassword_secret provided in config but "onetimepass" is not installed. ' + \
                      'run: pip install onetimepass'
                Common.dump_err(message=msg, exit_code=3)
            otp_value = otp.get_totp(self.get('okta_onetimepassword_secret'))

        if not otp_value:
            otp_value = click.prompt(
                text='Enter your multifactor authentication token',
                type=str,
                err=Common.to_std_error()
            )

        self.config_parameters['okta_onetimepassword'] = otp_value
