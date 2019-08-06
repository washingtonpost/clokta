""""
Code-behind the scenes for the cli application.
"""

from clokta.aws_cred_generator import AwsCredentialsGenerator
from clokta.common import Common
from clokta.okta_initiator import OktaInitiator
from clokta.clokta_configuration import CloktaConfiguration


class RoleAssumer(object):
    """ Core implementation of clokta """

    def __init__(self, profile):
        """
        :param profile: the name of the AWS profile the user wants to clokta into (e.g. pagebuilder)
        :type profile: str
        """
        self.profile = profile
        """folder to store files in"""
        self.data_dir = "~/.clokta/"

    def assume_role(self):
        """ entry point for the cli tool """
        clokta_config_file = self.data_dir + "clokta.cfg"
        clokta_config = CloktaConfiguration(profile_name=self.profile, clokta_config_file=clokta_config_file)

        # Attempt to initiate a connection using just cookies
        okta_initiator = OktaInitiator(data_dir=self.data_dir)
        result = okta_initiator.initiate_with_cookie(clokta_config)

        # If the cookie is expired or non-existent, INPUT_ERROR will be returned
        if result == OktaInitiator.Result.INPUT_ERROR:
            prompt_for_password = clokta_config.get('okta_password') is None
            mfas = []
            # Cookie didn't work.  Authenticate with Okta
            while result == OktaInitiator.Result.INPUT_ERROR:
                if prompt_for_password:
                    clokta_config.prompt_for(param_name='okta_password')
                result = okta_initiator.initiate_with_auth(clokta_config, mfas)
                prompt_for_password = True

            if result == OktaInitiator.Result.NEED_MFA:
                done = False
                force_mfa_prompt = False
                while not done:
                    chosen_factor = clokta_config.determine_mfa_mechanism(mfas, force_prompt=force_mfa_prompt)
                    need_otp = okta_initiator.initiate_mfa(factor=chosen_factor)
                    otp = clokta_config.determine_okta_onetimepassword(chosen_factor) if need_otp else None
                    result = okta_initiator.finalize_mfa(clokta_config=clokta_config, factor=chosen_factor, otp=otp)
                    done = result == OktaInitiator.Result.SUCCESS
                    force_mfa_prompt = True

        saml_assertion = okta_initiator.saml_assertion

        # We now have a SAML assertion and can generate a AWS Credentials
        aws_svc = AwsCredentialsGenerator(clokta_config=clokta_config,
                                          saml_assertion=saml_assertion,
                                          data_dir=self.data_dir)
        roles = aws_svc.get_roles()
        role = clokta_config.determine_role(roles)
        aws_svc.generate_creds(role)
        clokta_config.update_configuration()

        self.output_instructions(docker_file=aws_svc.docker_file, bash_file=aws_svc.bash_file)

    def output_instructions(self, docker_file, bash_file):
        if Common.get_output_format() == Common.quiet_out:
            Common.echo(
                message='export AWS_PROFILE={}'.format(self.profile),
                always_stdout=True
            )
        elif Common.get_output_format() == Common.long_out:
            Common.echo(
                message='AWS keys generated. To use with docker compose include\n\t{}\n'.format(docker_file) +
                        'To use with shell scripts source\n\t{}\n'.format(bash_file) +
                        'to use in the current interactive shell run\n\texport AWS_PROFILE={}\n'.format(self.profile)
            )
        else:
            Common.echo(
                message='Run "clokta -i" for steps to use generated credentials or just run\n' +
                        '\texport AWS_PROFILE={}'.format(self.profile)
            )
