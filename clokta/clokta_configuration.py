import base64
import getpass
import uuid

import click
import configparser
import enum
import json
import keyring
import os

from clokta.common import Common
from clokta.config_parameter import ConfigParameter
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

    KEYCHAIN_PATTERN = "clokta.{param_name}"  # The key in the keychain to use when storing a param

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
        self.param_list = self.__define_parameters()  # type: [ConfigParameter]
        self.parameters = {p.name: p for p in self.param_list}
        self.__initialize_configuration()

    def get(self, parameter_name):
        """
        Get the current value of a configuration parameter
        :param parameter_name: the name of the parameter
        :type parameter_name: str
        :return: the value of the parameter or None if not present
        """
        return self.parameters[parameter_name].value if parameter_name in self.parameters else None

    def update_configuration(self):
        """
        Write the current version of the configuration to the clokta.cfg file
        """
        clokta_cfg_file = configparser.ConfigParser()
        clokta_cfg_file.read(self.clokta_config_file)
        if not clokta_cfg_file.has_section(self.profile_name):
            clokta_cfg_file.add_section(self.profile_name)

        for param in self.param_list:
            if param.value:
                if param.save_to == ConfigParameter.SaveTo.DEFAULT:
                    clokta_cfg_file.set('DEFAULT', param.name, param.value)
                elif param.save_to == ConfigParameter.SaveTo.PROFILE:
                    clokta_cfg_file.set(self.profile_name, param.name, param.value)
                elif param.save_to == ConfigParameter.SaveTo.KEYRING:
                    try:
                        system = CloktaConfiguration.KEYCHAIN_PATTERN.format(param_name=param.name)
                        user = self.get('okta_username')
                        password = self.__obfuscate(param.value)
                        keyring.set_password(system, user, password)
                    except Exception as e:
                        Common.dump_err('WARNING: Could not save password to keychain: {}'.format(e))

        if Common.is_debug():
            Common.dump_out(
                message='Re-writing configuration file {}'.format(self.clokta_config_file)
            )
        self.__write_config(
            path_to_file=self.clokta_config_file,
            parser=clokta_cfg_file
        )

    def reset_default_role(self):
        # Clear it from the clokta.cfg file
        clokta_cfg_file = configparser.ConfigParser()
        clokta_cfg_file.read(self.clokta_config_file)
        clokta_cfg_file.remove_option(self.profile_name, 'okta_aws_role_to_assume')
        self.__write_config(
            path_to_file=self.clokta_config_file,
            parser=clokta_cfg_file
        )

        # And reset it
        self.parameters['okta_aws_role_to_assume'].value = None

    def __define_parameters(self):
        """
        Hard coded definition of all possible parameters
        :return: parameters without values
        :rtype: [ConfigParameter]
        """

        parameters = [
            ConfigParameter(
                name='okta_username',
                required=True,
                save_to=ConfigParameter.SaveTo.DEFAULT
            ),
            ConfigParameter(
                name='okta_org',
                required=True,
                save_to=ConfigParameter.SaveTo.DEFAULT,
                default_value='washpost.okta.com'
            ),
            ConfigParameter(
                name='multifactor_preference',
                save_to=ConfigParameter.SaveTo.DEFAULT,
                default_value='Okta Verify with Push'
            ),
            ConfigParameter(
                name='okta_aws_app_url',
                required=True,
                save_to=ConfigParameter.SaveTo.PROFILE
            ),
            ConfigParameter(
                name='okta_password',
                secret=True,
                save_to=ConfigParameter.SaveTo.KEYRING
            ),
            ConfigParameter(
                name='okta_aws_role_to_assume'
            ),
            ConfigParameter(
                name='okta_onetimepassword_secret',
                secret=True
            ),
            ConfigParameter(
                # aws_account_number is not really an input parameter, but
                # something we deduce during login and wanted to save in the clokta.cfg
                name='aws_account_number',
                save_to=ConfigParameter.SaveTo.PROFILE
            )
        ]
        return parameters

    def __initialize_configuration(self):
        """
        Load config file, both the desired section and the default section
        :return: the parameter list
        :rtype: dict
        """
        clokta_cfg_file = configparser.ConfigParser()
        clokta_cfg_file.read(self.clokta_config_file)

        # Make sure we have the bare minimum in the config file.  The DEFAULT section and the app URL.
        if not clokta_cfg_file['DEFAULT']:
            clokta_cfg_file['DEFAULT'] = {
                'okta_org': ''
            }
        if not clokta_cfg_file.has_section(self.profile_name):
            msg = 'No profile "{}" in clokta.cfg, but enter the information and clokta will create a profile.\n' + \
                  'Copy the link from the Okta App'
            app_url = click.prompt(text=msg.format(self.profile_name), type=str, err=Common.to_std_error()).strip()
            if not app_url.startswith("https://") or not app_url.endswith("?fromHome=true"):
                Common.dump_err(
                    "Invalid App URL.  URL usually of the form https://xxxxxxxx.okta.com/.../272?fromHome=true", 6
                )
                raise ValueError("Invalid URL")  # TODO: Handle with reprompt
            else:
                app_url = app_url[:-len("?fromHome=true")]
            clokta_cfg_file.add_section(self.profile_name)
            clokta_cfg_file.set(self.profile_name, 'okta_aws_app_url', app_url)

        config_section = clokta_cfg_file[self.profile_name]
        self.__load_parameters(config_section)

    def __prompt_for(self, param):
        prompt = param.prompt if param.prompt else 'Enter a value for {}'.format(param.name)
        if param.secret:
            field_value = getpass.getpass(prompt=prompt+":")
        else:
            field_value = click.prompt(text=prompt,
                                       type=str,
                                       err=Common.to_std_error(),
                                       default=param.default_value)
        return field_value

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

    def determine_mfa_mechanism(self, mfas, force_prompt):
        """
        Determine which of the passed in MFA mechanisms to use.  This may be specified
        by the configuration's 'multifactor_preference' if not prompt the user and put
        in the configuration
        :param mfas: possible mechanisms to use for MFA
        :type mfas: List[dict]
        :param force_prompt: whether to ignore any preconfigured default and prompt the user
        :type force_prompt: bool
        :return: the chosen MFA mechanism to use
        :rtype: dict
        """

        factor_preference = self.get('multifactor_preference')
        fact_chooser = FactorChooser(
            factors=mfas,
            factor_preference=factor_preference
        )

        chosen_factor = None
        # Is there only one legitimate MFA option available?
        if len(mfas) == 1:
            chosen_factor = fact_chooser.verify_only_factor(factor=mfas[0])

        if not chosen_factor:
            # Has the user pre-selected a legitimate factor?
            if factor_preference and not force_prompt:
                chosen_factor = fact_chooser.verify_preferred_factor()

        if not chosen_factor:
            chosen_factor = fact_chooser.choose_supported_factor()
            if chosen_factor:
                self.parameters['multifactor_preference'].value = chosen_factor['clokta_id']

        return chosen_factor

    def determine_role(self, possible_roles):
        """
        Determine which of several possible roles to assume by looking first in the config for a default role,
        and second by prompting the user.
        :param possible_roles: list of possible roles to assume
        :type possible_roles: List[AwsRole]
        :return: the role chosen
        :rtype: AwsRole
        """
        role_chooser = RoleChooser(
            possible_roles=possible_roles,
            role_preference=self.get('okta_aws_role_to_assume')
        )
        chosen_role, make_default = role_chooser.choose_role()
        self.parameters['okta_aws_role_to_assume'].value = chosen_role.role_arn
        if make_default:
            self.parameters['okta_aws_role_to_assume'].save_to = ConfigParameter.SaveTo.PROFILE
        # We also grab the account number out of the role ARN
        self.parameters['aws_account_number'].value = chosen_role.account
        return chosen_role

    def prompt_for(self, param_name):
        """
        Prompt the user for the parameter and store it in the configuration
        :param param_name: the name of the parameter
        :type param_name: str
        """
        param_to_prompt_for = self.parameters[param_name]
        param_to_prompt_for.value = self.__prompt_for(param_to_prompt_for)

    def determine_okta_onetimepassword(self, factor):
        """
        Get the one time password, which may be in one password or
        may need to be prompted for
        :param factor: the mfa mechanism being used.  Holds a user friendly label for identifying which mechanism.
        :type factor: dict
        :return: the Okta one time password
        :rtype: string
        """

        otp_value = None
        if self.get('okta_onetimepassword_secret'):
            try:
                # noinspection PyUnresolvedReferences
                import onetimepass as otp
            except ImportError:
                msg = 'okta_onetimepassword_secret provided in config but "onetimepass" is not installed. ' + \
                      'run: pip install onetimepass'
                Common.dump_err(message=msg)
                raise ValueError("Illegal configuration")
            otp_value = otp.get_totp(self.get('okta_onetimepassword_secret'))

        if not otp_value:
            otp_value = click.prompt(
                text='Enter your {} one time password'.format(factor['clokta_id']),
                type=str,
                err=Common.to_std_error(),
                default=''
            )
        return otp_value

    def __load_parameters(self, config_section):
        """
        For each parameter this will look first in the OS environment, then in the
        config file (which will look in both the section and in the DEFAULT section),
        then in the keychain (for secrets only) and then
        if still not found and the attribute is required, will prompt the user.
        :param config_section: section of the clokta.cfg file that represents the profile that we will
        login to though queries on this will also look in the DEFAULT section
        :type config_section:
        :return: a map of attributes that define the clokta login, e.g.
            {"okta_username": "doej", "okta_org": "washpost.okta.com", ...}
        :rtype: map[string, string]
        """
        debug_msg = 'Configuration:\n'
        for param in self.param_list:
            from_env = os.getenv(key=param.name, default=-1)
            if from_env != -1:
                # If defined in environment, use that first
                param.value = from_env
            elif param.name in config_section and config_section[param.name]:
                # If defined in the config file, make sure it's not a secret, otherwise use it
                if param.secret:
                    Common.dump_err(
                        message='Invalid configuration.  {} should never be defined in clokta.cfg.'.format(param.name))
                    raise ValueError("Illegal configuration")
                param.value = config_section[param.name]
            elif param.secret:
                system = CloktaConfiguration.KEYCHAIN_PATTERN.format(param_name=param.name)
                user = self.get('okta_username')
                try:
                    obfuscated = keyring.get_password(system, user)
                except Exception as e:
                    Common.dump_err('WARNING: Could not read password from keychain: {}'.format(e))
                param.value = self.__deobfuscate(obfuscated)

            if not param.value and param.required:
                # We need it.  Prompt for it.
                param.value = self.__prompt_for(param)
            debug_msg += '     {}={}'.format(param.name, param.value)

        if Common.is_debug():
            Common.dump_out(message=debug_msg)

    def __obfuscate(self, secret):
        """
        A real simple obfuscation so passwords don't appear in the keychain as plaintext
        This is not encryption and can easily be cracked or reverse engineered
        Counting on the keyring's security to protect the password
        :param secret: a secret to obfuscate
        :type secret: str
        :return: a obfuscated version that can be turned back into the secret with __deobfuscate
        :rtype: str
        """
        if not secret:
            return None

        key = str(uuid.getnode())
        enc = []
        for i in range(len(secret)):
            key_c = key[i % len(key)]
            enc_c = chr((ord(secret[i]) + ord(key_c)) % 256)
            enc.append(enc_c)
        return base64.urlsafe_b64encode("".join(enc).encode()).decode()

    def __deobfuscate(self, obfuscated):
        """
        Turn a string that was obfuscated with __obfuscate back into the original
        :param obfuscated: obfuscated string
        :type obfuscated: str
        :return: the original string
        :rtype: str
        """
        if not obfuscated:
            return None

        key = str(uuid.getnode())
        dec = []
        enc = base64.urlsafe_b64decode(obfuscated).decode()
        for i in range(len(enc)):
            key_c = key[i % len(key)]
            dec_c = chr((256 + ord(enc[i]) - ord(key_c)) % 256)
            dec.append(dec_c)
        return "".join(dec)

    @classmethod
    def dump_account_numbers(cls, clokta_config_file):
        clokta_cfg_file = configparser.ConfigParser()
        clokta_cfg_file.read(os.path.expanduser(clokta_config_file))
        section_names = clokta_cfg_file.sections()
        for section_name in section_names:
            if clokta_cfg_file.has_option(section=section_name, option='aws_account_number'):
                acct_num = clokta_cfg_file.get(section=section_name, option='aws_account_number')
                if acct_num:
                    Common.echo("{name} = {number}".format(name=section_name, number=acct_num))
