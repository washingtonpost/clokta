import os

from clokta.clokta_configuration import CloktaConfiguration
import json
import pickle
import requests
import time
from enum import Enum

from bs4 import BeautifulSoup

from clokta.common import Common


class OktaInitiator:

    # type hints used by PyCharm

    session_token: str

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
        self.data_dir = os.path.expanduser(data_dir)
        self.state = OktaInitiator.State.UNINITIALIZED
        self.saml_assertion = None  # type: str
        self.session_token = None  # type: str
        self.intermediate_state_token = None  # type: str
        self.factors = []  # type: [dict]

    def get_state(self):
        """
        :return: the state of the Okta connection.
        :rtype: OktaInitiator.State
        """
        return self.state

    def get_saml_assertion(self):
        """
        :return: the SAML token, or None if not successfully retrieved
        :rtype: str
        """
        return self.saml_assertion

    def initiate_with_cookie(self, clokta_config):
        """
        Request a SAML token from Okta without authenticating but relying on valid Okta cookie
        from a previous interaction.  If succesful state will be SUCCESS and you can get
        the SAML token.  If unsuccesful state will be FAIL.
        :param clokta_config: the configuration containing okta connection information
        :type clokta_config: CloktaConfiguration
        """
        self.saml_assertion = None
        self.state = OktaInitiator.State.FAIL  # Set to fail at start so exception leaves in fail state
        self.__request_saml_assertion(configuration=clokta_config)

    def initiate_with_auth(self, clokta_config):
        """
        Start the multistep process of getting a SAML token from Okta.  After this returns
        state will be NEED_MFA and you need to call initiate_mfa
        :param clokta_config: clokta configuration with okta connection information
        :type clokta_config: CloktaConfiguration
        :return: the list of MFA mechanisms to choose from
        :rtype: List[str]
        """
        self.saml_assertion = None
        self.state = OktaInitiator.State.FAIL  # Set to fail at start so exception leaves in fail state
        self.__auth_with_okta(
            configuration=clokta_config
        )

        # If no MFA was needed, then we've authed and can request SAML token
        if self.session_token:
            self.__request_saml_assertion(configuration=clokta_config, session_token=self.session_token)
            return []
        else:
            self.state = OktaInitiator.State.NEED_MFA
            return self.factors

    def initiate_mfa(self, clokta_config, factor):
        """
        Next step after initiate_with_auth in the multistep process of getting a SAML token from Okta.
        Some MFA mechanism, like SMS, need to perform an action before prompting the user for response.
        After this state will still be NEED_MFA and you need to call finalize_mfa
        :param clokta_config: clokta configuration with mfa response
        :type clokta_config: CloktaConfiguration
        :param factor: the MFA mechanism to use
        :type factor: dict
        :return: whether a one time password will be needed to complete MFA
        :rtype: bool
        """

        need_otp = True
        if factor['factorType'] == 'sms':
            self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=self.intermediate_state_token,
                otp_value=None
            )

        if factor['factorType'] == 'push':
            need_otp = False
            session_token = self.__do_mfa_with_push(
                factor=factor,
                state_token=self.intermediate_state_token
            )
            # Now that we have a session token, request the SAML token
            self.__request_saml_assertion(configuration=clokta_config, session_token=session_token)

        return need_otp

    def finalize_mfa(self, clokta_config, factor, otp):
        """
        Final step in multistep process of getting a SAML token from Okta.
        Submit MFA response to Okta
        :param clokta_config: clokta configuration with mfa response
        :type clokta_config: CloktaConfiguration
        :param factor: the MFA mechanism to use
        :type factor: dict
        :param otp: the one time password for MFA
        :type otp: str
        """

        session_token = self.__submit_mfa_response(factor=factor, otp=otp)

        if Common.is_debug():
            Common.dump_out(message='Okta session token: {}'.format(session_token))

        # Now that we have a session token, request the SAML token
        self.__request_saml_assertion(configuration=clokta_config, session_token=session_token)

    def __request_saml_assertion(self, configuration, session_token=None):
        """
        request saml 2.0 assertion
        :param configuration: the clokta configuration
        :type configuration: CloktaConfiguration
        :param session_token: a token returned by authenticating with okta.
            if None request will only work if there is a valid cookie
        :type session_token: str
        """
        self.saml_assertion = None
        response = self.__post_saml_request(
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
        for inputtag in soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                self.saml_assertion = inputtag.get('value')
        # If a session token is not passed in, we consider a failure as a normal possibility and just return None
        if not self.saml_assertion and session_token:
            if Common.is_debug():
                Common.dump_out(
                    'Expecting \'<input name="SAMLResponse" value="...">\' in Okta response, but not found.'
                )
            Common.dump_err(
                message='Unexpected response from Okta.',
                exit_code=4
            )

        self.state = OktaInitiator.State.SUCCESS if self.saml_assertion else OktaInitiator.State.FAIL

    def __post_saml_request(self, session_token, configuration):
        """
        Send request to SAML token to Okta
        :param session_token: the session token gotten from authenticating with Okta
        :type session_token: str
        :param configuration: the clokta configuration with 'okta_aws_app_url'
        :type configuration: CloktaConfiguration
        :return: the HTTP response
        :rtype: json str
        """
        cookie_file = self.data_dir + 'clokta.cookies'
        url = configuration.get('okta_aws_app_url')
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

    def __auth_with_okta(self, configuration):
        """
        Authenticate with Okta.  If no further info is required, return with session_token set.
        If MFA response is required, return with intermediate_state_token and factors set
        :param configuration: clokta configuration containing connection and user info
        :type configuration: CloktaConfiguration
        """
        self.session_token = None
        self.factors = []

        okta_response = None
        try:
            okta_response = self.__post_auth_request(configuration)
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

        if 'sessionToken' in okta_response and okta_response['sessionToken']:
            # MFA wasn't required.  We've got the token.
            self.session_token = okta_response['sessionToken']
        elif 'status' in okta_response and okta_response['status'] == 'MFA_ENROLL':
            # handle case where MFA is required but no factors have been enabled
            msg = 'Please enroll in multi-factor authentication before using this tool'
            Common.dump_err(message=msg, exit_code=3)
        elif 'status' in okta_response and okta_response['status'] == 'MFA_REQUIRED':
            self.factors = okta_response['_embedded']['factors']
            if not self.factors:
                # Another case where no factors have been enabled
                msg = 'No MFA factors have been set up for this account'
                Common.dump_err(message=msg, exit_code=3)
            self.intermediate_state_token = okta_response['stateToken']
        else:
            msg = 'Unexpected response from Okta authentication request'
            Common.dump_err(message=msg, exit_code=3)

    def __post_auth_request(self, configuration):
        """
        Posts a credentials-based authentication to Okta and returns an HTTP response
        :param configuration: clokta configuration with okta connection info
        :type configuration: CloktaConfiguration
        :return: the text from the HTTP response as a json blob
        :rtype: dict
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Cache-Control': '"no-cache',
            'Authorization': 'API_TOKEN'
        }
        payload = {
            'username': configuration.get('okta_username'),
            'password': configuration.get('okta_password')
        }
        url = 'https://' + configuration.get('okta_org') + '/api/v1/authn'

        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            resp = json.loads(response.text)
            return resp
        else:
            response.raise_for_status()

    def __wait_for_push_result(self, state_token, push_response):
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

    def __submit_mfa_response(self, factor, otp):
        """
        post one time password to Okta
        :param factor: the MFA mechanism to use
        :type factor: dict
        :param otp: the one time password for MFA
        :type otp: str
        """
        session_token = None
        try:
            mfa_response = self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=self.intermediate_state_token,
                otp_value=otp
            )
            session_token = mfa_response['sessionToken']
        except requests.exceptions.HTTPError as http_err:
            msg = 'Okta returned this MFA related error: {}'.format(http_err)
            Common.dump_err(message=msg, exit_code=1)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg, exit_code=2)

        return session_token

    def __do_mfa_with_push(self, factor, state_token):
        """
        Send push re: Okta Verify
        :param factor: mfa information
        :type factor: dict
        :param state_token: token used in MFA back and forth
        :type: str
        :return: the session token
        :rtype: str
        """
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
                return self.__wait_for_push_result(
                    state_token=state_token,
                    push_response=response_data
                )
