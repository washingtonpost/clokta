""" ConfigGenerator class must be instantiated prior to use """
import copy
import getpass
import json
import os

import click

from clokta.common import Common


class ConfigGenerator(object):
    """
    Loads or otherwise generates configuration information
    """

    config_fields = [
        {
            'name': 'okta_username',
            'required': True,
            'save_to': 'default'
        }, {
            'name': 'okta_org',
            'required': True,
            'save_to': 'default',
            'default_value': 'washpost.okta.com'
        }, {
            'name': 'multifactor_preference',
            'required': True,
            'save_to': 'default',
            'default_value': "Okta Verify with Push",
            'prompt': (
                'Enter a preferred MFA - choose between Google Authenticator, SMS text message, '
                'Okta Verify, or Okta Verify with Push'
            )
        }, {
            'name': 'okta_aws_app_url',
            'required': True,
            'save_to': 'profile'
        }, {
            'name': 'okta_password',
            'secret': True
        }, {
            'name': 'okta_aws_role_to_assume'
        }, {
            'name': 'okta_onetimepassword_secret',
            'secret': True
        }
    ]

    @classmethod
    def generate_configuration(cls, config_section):
        """
        This creates a dictionary of all the necessary attributes for cloktaing into an account
        For each attribute it will look first in the OS environment, then in the passed in
        config file (which will look in both the section and in the DEFAULT section) and then
        if still not found and the attribute is required, will prompt the user.
        :param config_section: section of the clokta.cfg file that represents the profile that we will
        login to though queries on this will also look in the DEFAULT section
        :type config_section:
        :return: a map of attributes that define the clokta login, e.g.
            {"okta_username": "doej", "okta_org": "washpost.okta.com", ...}
        :rtype: map[string, string]
        """
        configuration = {}
        for field in ConfigGenerator.config_fields:
            key = field['name']
            is_secret = 'secret' in field and field['secret']
            from_env = os.getenv(key=key, default=-1)
            if from_env != -1:
                # If defined in environment, use that first
                configuration[key] = from_env
            elif key in config_section and config_section[key]:
                # If defined in the config file, make sure it's not a secret, otherwise use it
                if is_secret:
                    Common.dump_err(
                        message='Invalid configuration.  {} should never be defined in clokta.cfg.'.format(key),
                        exit_code=6)
                configuration[key] = config_section[key]
            elif 'required' in field and field['required']:
                    # We need it.  Prompt for it.
                    configuration[key] = ConfigGenerator.prompt_for(key)

        if Common.is_debug():
            copy_config = copy.deepcopy(configuration)
            for key in copy_config:
                if key.endswith('password'):
                    copy_config[key] = '<redacted>'
            msg = 'Configuration: {}'.format(
                json.dumps(obj=copy_config, indent=4)
            )
            Common.dump_out(message=msg)

        return configuration

    @classmethod
    def prompt_for(cls, field_name):
        fields = [field for field in ConfigGenerator.config_fields if field['name']==field_name]
        field = fields[0] if fields else {}
        prompt = field['prompt'] if 'prompt' in field and field['prompt'] is not '' else 'Enter a value for {}'.format(field_name)
        if 'secret' in field and field['secret']:
            field_value = getpass.getpass(prompt=prompt+":")
        else:
            field_value = click.prompt(text=prompt,
                                       type=str,
                                       err=Common.to_std_error(),
                                       default=field['default_value'] if 'default_value' in field else None)
        return field_value