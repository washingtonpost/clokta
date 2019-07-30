import click  # TODO REMOVE
from clokta.factor_chooser import FactorChooser  # TODO REMOVE
import json
import pickle
import requests
import time
from enum import Enum

from bs4 import BeautifulSoup

from clokta.common import Common


class OktaInitiator:

    class State(Enum):
        UNINITIALIZED = 0
        FAIL = 1
        NEED_MFA = 2
        SUCCESS = 3

    def __init__(self, data_dir):
        """
        This class initiates connections with Okta.
        Once you attempt to initiate a connection this object has three states
        1) Failed - you can query the failed state or try again
        2) Waiting on MFA - you can submit MFA credentials
        3) Succeeded - you can retrieve the SAML token

        :param data_dir: the directory to store the cookies file
        :type data_dir: str
        """
        self.data_dir = data_dir
        self.state = OktaInitiator.State.UNINITIALIZED
        self.saml_assertion = None

    def initiate_with_cookie(self, clokta_config):
        self.saml_assertion = self.__saml_assertion_aws(
            session_token=None,
            configuration=clokta_config.config_parameters  # TODO: Pass in whole config
        )
        self.state = OktaInitiator.State.SUCCESS if self.saml_assertion else OktaInitiator.State.FAIL

    def initiate_with_auth(self, clokta_config):
        session_token = self.__okta_session_token(
            configuration=clokta_config.config_parameters  # TODO: Pass in whole config
        )
        if Common.is_debug():
            Common.dump_out(message='Okta session token: {}'.format(session_token))

        self.saml_assertion = self.__saml_assertion_aws(
            session_token=session_token,
            configuration=clokta_config.config_parameters  # TODO: Pass in whole config
        )

    def __saml_assertion_aws(self, session_token, configuration):
        """
        fetch saml 2.0 assertion
        """
        response = self.__okta_app_response(
            session_token=session_token,
            configuration=configuration
        )

        if Common.is_debug():
            Common.dump_out(
                message='SAML response {} session token: {}'.format(
                    "with" if session_token else "without", response.content
                )
            )

        soup = BeautifulSoup(response.content, "html.parser")
        assertion = None
        for inputtag in soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                assertion = inputtag.get('value')
        # If a session token is not passed in, we consider a failure as a normal possibility and just return None
        if not assertion and session_token:
            if Common.is_debug():
                Common.dump_out(
                    'Expecting \'<input name="SAMLResponse" value="...">\' in Okta response, but not found.'
                )
            Common.dump_err(
                message='Unexpected response from Okta.',
                exit_code=4
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
        except Exception:
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

    def __okta_session_token(self, configuration):
        """Authenticate with Okta; receive a session token"""
        okta_response = None

        try:
            okta_response = self.__okta_auth_response(configuration=configuration)
        except requests.exceptions.HTTPError as http_err:
            if Common.is_debug():
                msg = 'Okta returned this credentials/password related error: {}\n' + \
                      'This could be a mistyped password or a misconfigured username ' + \
                      'or URL.'.format(http_err)
            else:
                msg = "Failure.  Wrong password or misconfigured session."
            Common.dump_err(message=msg, exit_code=1)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg, exit_code=2)

        # handle case where MFA is required but no factors have been enabled
        if okta_response['status'] == 'MFA_ENROLL':
            msg = 'Please enroll in multi-factor authentication before using this tool'
            Common.dump_err(message=msg, exit_code=3)

        otp_value = None
        if configuration.get('okta_onetimepassword_secret'):
            try:
                # noinspection PyUnresolvedReferences
                import onetimepass as otp
            except ImportError:
                msg = 'okta_onetimepassword_secret provided in config but "onetimepass" is not installed. ' + \
                      'run: pip install onetimepass'
                Common.dump_err(message=msg, exit_code=3)
            otp_value = otp.get_totp(configuration['okta_onetimepassword_secret'])

        if okta_response['status'] == 'MFA_REQUIRED':
            factors = okta_response['_embedded']['factors']
            if factors:
                return self.__okta_session_token_mfa(
                    auth_response=okta_response,
                    factors=factors,
                    factor_preference=configuration['multifactor_preference'],
                    otp_value=otp_value
                )
            else:
                msg = 'No MFA factors have been set up for this account'
                Common.dump_err(message=msg, exit_code=3)

        return okta_response['sessionToken']

    def __okta_auth_response(self, configuration):
        """Returns an HTTP response for credentials-based authentication with Okta"""
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

    def __okta_session_token_mfa(self, auth_response, factors, factor_preference, otp_value=None):
        """Determine which factor to use and apply it to get a session token"""
        session_token = None
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
            otp_value = click.prompt(text='Enter your multifactor authentication token', type=str, err=Common.to_std_error())
        try:
            mfa_response = self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=state_token,
                otp_value=otp_value
            )
            session_token = mfa_response['sessionToken']
        except requests.exceptions.HTTPError as http_err:
            msg = 'Okta returned this MFA related error: {}'.format(http_err)
            Common.dump_err(message=msg, exit_code=1)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg, exit_code=2)

        return session_token

    def __send_push(self, factor, state_token):
        """Send push re: Okta Verify"""
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
        """Wait for push response acknowledgement"""
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
        """Automatically choose, or allow user to choose, the MFA option"""

        fact_chooser = FactorChooser(
            factors=factors,
            factor_preference=factor_preference
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
        """Sends the MFA token entered and retuns the response"""
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
