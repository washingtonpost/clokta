""""
Code-behind the scenes for the cli application.
"""
import os

import boto3
from botocore.exceptions import ClientError

from clokta.common import Common
from clokta.factor_chooser import FactorChooser
from clokta.okta_initiator import OktaInitiator
from clokta.role_chooser import RoleChooser
from clokta.profile_manager import ProfileManager


class RoleAssumer(object):
    """ Core implementation of clokta """

    def __init__(self, profile):
        """
        :param profile: the name of the AWS profile the user wants to clokta into (e.g. pagebuilder)
        :type profile: str
        """
        self.profile = profile
        """folder to store files in"""
        self.data_dir = None

    def assume_role(self):
        """ entry point for the cli tool """
        profile_mgr = ProfileManager(profile_name=self.profile)
        profile_mgr.update_configuration()

        # Need a directory to store intermediate files.  Use the same directory that clokta configuration
        # is kept in
        self.data_dir = os.path.dirname(profile_mgr.config_location)

        # Attempt to initiate a connection using just cookies
        okta_initiator = OktaInitiator(self.data_dir)
        okta_initiator.initiate_with_cookie(profile_mgr)

        #
        #
        #
        configuration = profile_mgr.getParameters()
        #
        #

        if okta_initiator.state == OktaInitiator.State.FAIL:
            if 'okta_password' not in configuration or not configuration['okta_password']:
                configuration['okta_password'] = profile_mgr.prompt_for('okta_password')

            okta_initiator.initiate_with_auth(profile_mgr)

        saml_assertion = okta_initiator.saml_assertion

        idp_and_role_chooser = RoleChooser(
            saml_assertion=saml_assertion,
            role_preference=configuration.get('okta_aws_role_to_assume')
        )
        idp_role_tuple = idp_and_role_chooser.choose_idp_role_tuple()

        client = boto3.client('sts')
        # Try for a 12 hour session.  If it fails, try for shorter periods
        durations = [43200, 14400, 3600]
        for duration in durations:
            try:
                assumed_role_credentials = client.assume_role_with_saml(
                    RoleArn=idp_role_tuple[2],
                    PrincipalArn=idp_role_tuple[1],
                    SAMLAssertion=saml_assertion,
                    DurationSeconds=duration
                )
                if duration == 3600:
                    Common.echo(message='YOUR SESSION WILL ONLY LAST ONE HOUR')
                break
            except ClientError as e:
                # If we get a validation error and we have shorter durations to try, try a shorter duration
                if e.response['Error']['Code'] != 'ValidationError' or duration == durations[-1]:
                    raise

        profile_mgr.apply_credentials(credentials=assumed_role_credentials)
        bash_file = profile_mgr.write_sourceable_file(credentials=assumed_role_credentials)
        docker_file = profile_mgr.write_dockerenv_file(credentials=assumed_role_credentials)
        self.output_instructions(docker_file=docker_file, bash_file=bash_file)

    def output_instructions(self, docker_file, bash_file):
        if Common.get_output_format()==Common.quiet_out:
            Common.echo(
                message='export AWS_PROFILE={}'.format(self.profile),
                always_stdout=True
            )
        elif Common.get_output_format()==Common.long_out:
            Common.echo(
                message='AWS keys generated. To use with docker compose include\n\t{}\n'.format(docker_file) +
                        'To use with shell scripts source\n\t{}\n'.format(bash_file) +
                        'to use in the current interactive shell run\n\texport AWS_PROFILE={}\n'.format(self.profile)
            )
        else:
            Common.echo(
                message='Run "clokta -i" for steps to use generated credentials or just run\n\texport AWS_PROFILE={}'.format(self.profile)
            )


