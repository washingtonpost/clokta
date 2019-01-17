'''
Code-behind the scenes for the cli application.
'''
import json
import os
import pickle
import time

import boto3
from botocore.exceptions import ClientError
import click
import requests
from bs4 import BeautifulSoup

from clokta.common import Common
from clokta.factor_chooser import FactorChooser
from clokta.role_chooser import RoleChooser
from clokta.profile_manager import ProfileManager


class RoleAssumer(object):
    ''' Core implementation of clokta '''

    def __init__(self, profile, verbose=False):
        ''' Constructor '''
        self.profile = profile
        self.verbose = verbose
        self.data_dir = None

    def assume_role(self):
        ''' entry point for the cli tool '''
        profile_mgr = ProfileManager(profile_name=self.profile, verbose=self.verbose)
        configuration = profile_mgr.initialize_configuration()
        profile_mgr.update_configuration(profile_configuration=configuration)

        # Need a directory to store intermediate files.  Use the same directory that clokta configuration
        # is kept in
        self.data_dir = os.path.dirname(profile_mgr.config_location)

        saml_assertion = self.__saml_assertion_aws(
            session_token=None,
            configuration=configuration
        )

        if not saml_assertion:
            if 'okta_password' not in configuration or not configuration['okta_password']:
                configuration['okta_password'] = profile_mgr.prompt_for('okta_password')

            session_token = self.__okta_session_token(
                configuration=configuration
            )
            if self.verbose:
                Common.dump_verbose(message='Okta session token: {}'.format(session_token))

            saml_assertion = self.__saml_assertion_aws(
                session_token=session_token,
                configuration=configuration
            )

        idp_and_role_chooser = RoleChooser(
            saml_assertion=saml_assertion,
            role_preference=configuration.get('okta_aws_role_to_assume'),
            verbose=self.verbose
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

        profile_mgr.apply_credentials(credentials=assumed_role_credentials, echo_message=True)
        bash_file = profile_mgr.write_sourceable_file(credentials=assumed_role_credentials)
        docker_file = profile_mgr.write_dockerenv_file(credentials=assumed_role_credentials)
        Common.echo(
            message='AWS keys generated. To use, run "export AWS_PROFILE={prof}"\nor use files {file1} with docker compose or {file2} with shell scripts'.format(
                prof=self.profile, file1=docker_file, file2=bash_file
            )
        )

    def __okta_session_token(self, configuration):
        ''' Authenticate with Okta; receive a session token '''
        okta_response = None

        try:
            okta_response = self.__okta_auth_response(configuration=configuration)
        except requests.exceptions.HTTPError as http_err:
            if self.verbose:
                msg = 'Okta returned this credentials/password related error: {}\nThis could be a mistyped password or a misconfigured username or URL.'.format(http_err)
            else:
                msg = "Failure.  Wrong password or misconfigured session."
            Common.dump_err(message=msg, exit_code=1, verbose=self.verbose)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg, exit_code=2, verbose=self.verbose)

        # handle case where MFA is required but no factors have been enabled
        if okta_response['status'] == 'MFA_ENROLL':
            msg = 'Please enroll in multi-factor authentication before using this tool'
            Common.dump_err(message=msg, exit_code=3, verbose=self.verbose)

        otp_value = None
        if configuration.get('okta_onetimepassword_secret'):
            try:
                import onetimepass as otp
            except ImportError:
                msg = 'okta_onetimepassword_secret provided in config but "onetimepass" is not installed. run: pip install onetimepass'
                Common.dump_err(message=msg, exit_code=3, verbose=self.verbose)
            otp_value = otp.get_totp(configuration['okta_onetimepassword_secret'])

        if okta_response['status'] == 'MFA_REQUIRED':
            factors = okta_response['_embedded']['factors']
            if factors:
                return self.__okta_session_token_mfa(
                    auth_response=okta_response,
                    factors=factors,
                    factor_preference=configuration['multifactor_preference'],
                    otp_value = otp_value
                )
            else:
                msg = 'No MFA factors have been set up for this account'
                Common.dump_err(message=msg, exit_code=3, verbose=self.verbose)

        return okta_response['sessionToken']

    def __okta_session_token_mfa(self, auth_response, factors, factor_preference, otp_value=None):
        ''' Determine which factor to use and apply it to get a session token '''
        factor = self.__choose_factor(
            factors=factors,
            factor_preference=factor_preference,
        )
        state_token = auth_response['stateToken']

        if factor['factorType'] == 'push':
            return self.__send_push(
                factor=factor,
                state_token=state_token
            )

        if factor['factorType'] == 'sms':
            self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=state_token,
                otp_value=None
            )

        if not otp_value:
            otp_value = click.prompt('Enter your multifactor authentication token', type=str)
        try:
            mfa_response = self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=state_token,
                otp_value=otp_value
            )
            session_token = mfa_response['sessionToken']
        except requests.exceptions.HTTPError as http_err:
            msg = 'Okta returned this MFA related error: {}'.format(http_err)
            Common.dump_err(message=msg, exit_code=1, verbose=self.verbose)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg, exit_code=2, verbose=self.verbose)

        return session_token

    def __send_push(self, factor, state_token):
        ''' Send push re: Okta Verify '''
        url = factor['_links']['verify']['href']
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache-Control': '"no-cache'
        }
        payload = {
            'stateToken': state_token
        }

        response_data = None
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            response_data = response.json()
        else:
            response.raise_for_status()

        Common.echo(message='Push notification sent; waiting for your response', new_line=False)

        status = response_data['status']
        if status == 'MFA_CHALLENGE':
            if 'factorResult' in response_data and response_data['factorResult'] == 'WAITING':
                return self.__check_push_result(
                    state_token=state_token,
                    push_response=response_data
                )

    def __check_push_result(self, state_token, push_response):
        ''' Wait for push response acknowledgement '''
        url = push_response['_links']['next']['href']
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache-Control': '"no-cache'
        }
        payload = {
            'stateToken': state_token
        }

        wait_for = 60
        timeout = time.time() + wait_for
        response_data = None
        while True:
            Common.echo(message='.', new_line=False)
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            if response.status_code == requests.codes.ok:  # pylint: disable=E1101
                response_data = response.json()
            else:
                response.raise_for_status()

            if 'sessionToken' in response_data or time.time() > timeout:
                break
            time.sleep(3)

        if response_data and 'sessionToken' in response_data:
            Common.echo(message='Session confirmed')
            return response_data['sessionToken']
        else:
            msg = 'Timeout expired ({} seconds)'.format(wait_for)
            Common.dump_err(message=msg, exit_code=3)

    def __choose_factor(self, factors, factor_preference=None):
        ''' Automatically choose, or allow user to choose, the MFA option '''

        fact_chooser = FactorChooser(
            factors=factors,
            factor_preference=factor_preference,
            verbose=self.verbose
        )

        # Is there only one legitimate MFA option available?
        if len(factors) == 1:
            factor = fact_chooser.verify_only_factor(factor=factors[0])
            if factor:
                return factor

        # Has the user pre-selected a legitimate factor?
        if factor_preference:
            factor = fact_chooser.verify_preferred_factor()
            if factor:
                return factor

        return fact_chooser.choose_supported_factor()

    def __okta_mfa_verification(self, factor_dict, state_token, otp_value=None):
        ''' Sends the MFA token entered and retuns the response '''
        url = factor_dict['_links']['verify']['href']
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache-Control': '"no-cache'
        }
        payload = {
            'stateToken': state_token
        }
        if otp_value:
            payload['answer'] = otp_value

        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            return response.json()
        else:
            response.raise_for_status()

    def __okta_auth_response(self, configuration):
        ''' Returns an HTTP response for credentials-based authentication with Okta '''
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache-Control': '"no-cache',
            'Authorization': 'API_TOKEN'
        }
        payload = {
            'username': configuration['okta_username'],
            'password': configuration['okta_password']
        }
        url = 'https://' + configuration['okta_org'] + '/api/v1/authn'

        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            resp = json.loads(response.text)
            return resp
        else:
            response.raise_for_status()

    def __saml_assertion_aws(self, session_token, configuration):
        ''' fetch saml 2.0 assertion '''
        response = self.__okta_app_response(
            session_token=session_token,
            configuration=configuration
        )

        if self.verbose:
            Common.dump_verbose(
                message='SAML response {} session token: {}'.format("with" if session_token else "without", response.content)
            )

        soup = BeautifulSoup(response.content, "html.parser")
        assertion = None
        for inputtag in soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                assertion = inputtag.get('value')
        # If a session token is not passed in, we consider a failure as a normal possibility and just return None
        if not assertion and session_token:
            if self.verbose:
                Common.dump_verbose('Expecting \'<input name="SAMLResponse" value="...">\' in Okta response, but not found.')
            Common.dump_err(
                message='Unexpected response from Okta.',
                exit_code=4,
                verbose=self.verbose
            )
        return assertion

    def __okta_app_response(self, session_token, configuration):
        cookie_file = self.data_dir + '/clokta.cookies'
        url = configuration['okta_aws_app_url']
        if session_token:
            url += '?onetimetoken=' + session_token
        try:
            with open(cookie_file, 'rb') as f:
                cookies = pickle.load(f)
        except:
            cookies = None
        response = requests.get(url, cookies=cookies)

        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            if not cookies:
                cookies = response.cookies
            else:
                cookies.update(response.cookies)
            with open(cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
                return response
        else:
            response.raise_for_status()
