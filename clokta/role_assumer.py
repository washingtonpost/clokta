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
        clokta_config.update_configuration()

        # Attempt to initiate a connection using just cookies
        okta_initiator = OktaInitiator(data_dir=self.data_dir)
        okta_initiator.initiate_with_cookie(clokta_config)

        if okta_initiator.state == OktaInitiator.State.FAIL:
            # Cookie didn't work.  Prompt for the password and try authenticating with Okta
            clokta_config.determine_password()
            mfas = okta_initiator.initiate_with_auth(clokta_config)

            if okta_initiator.get_state() == OktaInitiator.State.NEED_MFA:
                chosen_factor = clokta_config.determine_mfa_mechanism(mfas)
                need_otp = okta_initiator.initiate_mfa(clokta_config=clokta_config, factor=chosen_factor)
                if need_otp:
                    otp = clokta_config.determine_okta_onetimepassword()
                    okta_initiator.finalize_mfa(clokta_config=clokta_config, factor=chosen_factor, otp=otp)

        if okta_initiator.state == OktaInitiator.State.FAIL:
            msg = 'Failed to authenticate with Okta'
            Common.dump_err(message=msg, exit_code=10)

        saml_assertion = okta_initiator.saml_assertion

        # We now have a SAML assertion and can generate a AWS Credentials
        aws_svc = AwsCredentialsGenerator(clokta_config=clokta_config,
                                          saml_assertion=saml_assertion,
                                          data_dir=self.data_dir)
        roles = aws_svc.get_roles()
        role = clokta_config.determine_role(roles)
        aws_svc.generate_creds(role)

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
