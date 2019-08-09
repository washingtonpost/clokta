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

    class Result(Enum):
        INPUT_ERROR = 1
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
        self.saml_assertion = None  # type: str
        self.session_token = None  # type: str
        self.intermediate_state_token = None  # type: str
        self.factors = []  # type: [dict]

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
        :return: SUCCESS if succesfully got SAML token or INPUT_ERROR if cookie expired.
        Any other problem thows an exception.
        """
        self.saml_assertion = None
        result = self.__request_saml_assertion(configuration=clokta_config, use_session_token=False)
        return result

    def initiate_with_auth(self, clokta_config, mfas_to_fill):
        """
        Start the multistep process of getting a SAML token from Okta.  After this you need to
        call initiate_mfa
        :param clokta_config: clokta configuration with okta connection information
        :type clokta_config: CloktaConfiguration
        :param mfas_to_fill: an empty list that this will fill with possible MFA mechanisms
        :type mfas_to_fill: List[dict]
        :return: SUCCESS if successfully obtained SAML token, NEED_MFA if successfully identified user
        and retrieved MFA options, or FAIL if could not identify user because of bad password
        Any other result raises an exception
        """
        self.saml_assertion = None
        result = self.__auth_with_okta(
            configuration=clokta_config
        )

        # If no MFA was needed, then we've authed and can request SAML token
        if result == OktaInitiator.Result.SUCCESS:
            self.__request_saml_assertion(configuration=clokta_config, use_session_token=True)
        elif result == OktaInitiator.Result.NEED_MFA:
            mfas_to_fill[:] = self.factors
        return result

    def initiate_mfa(self, factor):
        """
        Next step after initiate_with_auth in the multistep process of getting a SAML token from Okta.
        Some MFA mechanism, like SMS, need to perform an action before prompting the user for response.
        After this state will still be NEED_MFA and you need to call finalize_mfa
        :param factor: the MFA mechanism to use
        :type factor: dict
        :return: whether a one time password will be needed to complete MFA
        :rtype: bool
        """

        if factor['factorType'] == 'sms':
            self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=self.intermediate_state_token,
                otp_value=None
            )

        need_otp = factor['factorType'] != 'push'
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
        :return: SUCCESS if succesfully authenticated.  INPUT_ERROR if the otp was not correct.
        """

        if factor['factorType'] == 'push':
            result = self.__do_mfa_with_push(
                factor=factor,
                state_token=self.intermediate_state_token
            )
        else:
            result = self.__submit_mfa_response(factor=factor, otp=otp)

        if result == OktaInitiator.Result.SUCCESS:
            if Common.is_debug():
                Common.dump_out(message='Okta session token: {}'.format(self.session_token))

            # Now that we have a session token, request the SAML token
            self.__request_saml_assertion(configuration=clokta_config, use_session_token=True)
        return result

    def __request_saml_assertion(self, configuration, use_session_token):
        """
        request saml 2.0 assertion
        :param configuration: the clokta configuration
        :type configuration: CloktaConfiguration
        :param use_session_token: whether to submit a session token with the request.
        The session token will be obtained from self.session_token
        :type use_session_token: bool
        :return: SUCCESS if succesfully got SAML token or INPUT_ERROR if cookie expired.
        Any other problem thows an exception.
        """
        self.saml_assertion = None
        if use_session_token and not self.session_token:
            raise ValueError("No session token to use")

        response = self.__post_saml_request(
            use_session_token=use_session_token,
            configuration=configuration
        )

        if Common.is_debug():
            Common.dump_out(
                message='Requested SAML assertion from Okta {} session token.\nResponse: {}'.format(
                    "with" if use_session_token else "without", response.content
                )
            )

        soup = BeautifulSoup(response.content, "html.parser")
        for inputtag in soup.find_all('input'):
            if inputtag.get('name') == 'SAMLResponse':
                self.saml_assertion = inputtag.get('value')

        if not self.saml_assertion:
            if not use_session_token:
                # If a session token is not passed in, we consider a failure as a normal possibility
                if Common.is_debug():
                    Common.dump_out('Request without session token rejected.')
                return OktaInitiator.Result.INPUT_ERROR
            else:
                if Common.is_debug():
                    Common.dump_out(
                        'Expecting \'<input name="SAMLResponse" value="...">\' in Okta response, but not found.'
                    )
                raise RuntimeError('Unexpected response from Okta.')
        else:
            return OktaInitiator.Result.SUCCESS

    def __post_saml_request(self, use_session_token, configuration):
        """
        Send request to SAML token to Okta
        :param use_session_token: whether to pass a session token gotten from authenticating with Okta
        :type use_session_token: bool
        :param configuration: the clokta configuration with 'okta_aws_app_url'
        :type configuration: CloktaConfiguration
        :return: the HTTP response
        :rtype: json str
        """
        cookie_file = self.data_dir + 'clokta.cookies'
        url = configuration.get('okta_aws_app_url')
        if use_session_token:
            url += '?onetimetoken=' + self.session_token
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
        Authenticate with Okta.  If no further info is required, return SUCCESS with session_token set.
        If MFA response is required, return NEED_MFA with intermediate_state_token and factors set
        A rejection from Okta is interpretted as a bad password and INPUT_ERROR is returned.
        :param configuration: clokta configuration containing connection and user info
        :type configuration: CloktaConfiguration
        :return: SUCCESS, NEED_MFA or INPUT_ERROR
        :rtype: OktaInitiator.Result
        """
        self.session_token = None
        self.factors = []

        try:
            okta_response = self.__post_auth_request(configuration)
        except requests.exceptions.HTTPError as http_err:
            if Common.is_debug():
                Common.dump_out(
                    ('Okta returned this credentials/password related error: {}\n' +
                        'This could be a mistyped password or a misconfigured username ' +
                        'or URL.').format(http_err))
            return OktaInitiator.Result.INPUT_ERROR
        except Exception as err:
            Common.dump_err('Unexpected error authenticating with Okta: {}'.format(err))
            raise

        if 'sessionToken' in okta_response and okta_response['sessionToken']:
            # MFA wasn't required.  We've got the token.
            self.session_token = okta_response['sessionToken']
            return OktaInitiator.Result.SUCCESS
        elif 'status' in okta_response and okta_response['status'] == 'MFA_ENROLL':
            # handle case where MFA is required but no factors have been enabled
            Common.dump_err('Please enroll in multi-factor authentication before using this tool')
            raise ValueError("No MFA mechanisms configured")
        elif 'status' in okta_response and okta_response['status'] == 'MFA_REQUIRED':
            self.factors = okta_response['_embedded']['factors']
            if not self.factors:
                # Another case where no factors have been enabled
                raise ValueError("No MFA mechanisms configured")
            self.intermediate_state_token = okta_response['stateToken']
            return OktaInitiator.Result.NEED_MFA
        else:
            Common.dump_err('Unexpected response from Okta authentication request')
            raise RuntimeError("Unexpected response from Okta")

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
        if Common.is_debug():
            Common.dump_out(
                'Requested password-based authentication with Okta.\n' +
                'Response: {}'.format(response.content))

        if response.status_code == requests.codes.ok:  # pylint: disable=E1101
            resp = json.loads(response.text)
            return resp
        else:
            response.raise_for_status()

    def __wait_for_push_result(self, state_token, push_response):
        """
        A request was sent to Okta querying the status of a push.  Process the response, pull the session
        token from it, and store in self.session_token
        :param state_token: a token received from Okta identifying this authentication attempt session
        :type state_token: str
        :param push_response: the HTTP response from the HTTP request
        :type push_response: json
        :return: SUCCESS if response indicates SUCCESS.  INPUT_ERROR if timed out.
        """
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
            self.session_token = response_data['sessionToken']
            return OktaInitiator.Result.SUCCESS
        else:
            msg = 'Timeout expired ({} seconds)'.format(wait_for)
            Common.dump_err(message=msg)
            return OktaInitiator.Result.INPUT_ERROR

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

        data = json.dumps(payload)
        if Common.is_debug():
            Common.dump_out("Sending MFA verification to...\nurl: {}\nbody: {}".format(url, data))
        response = requests.post(url, data=data, headers=headers)
        if Common.is_debug():
            Common.dump_out(
                "Received {} response from Okta: {}".format(response.status_code, json.dumps(response.json()))
            )
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
        :return: SUCCESS if received a session token from Okta.  INPUT_ERROR if Okta reports incorrect
        one time password
        :rtype: OktaInitiator.Result
        """
        self.session_token = None
        try:
            mfa_response = self.__okta_mfa_verification(
                factor_dict=factor,
                state_token=self.intermediate_state_token,
                otp_value=otp
            )
            self.session_token = mfa_response['sessionToken']
            return OktaInitiator.Result.SUCCESS
        except requests.exceptions.HTTPError as http_err:
            Common.dump_err('Okta returned this MFA related error: {}'.format(http_err))
            return OktaInitiator.Result.INPUT_ERROR
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            Common.dump_err(message=msg)
            raise ValueError("Unexpected error with MFA")

    def __do_mfa_with_push(self, factor, state_token):
        """
        Send push re: Okta Verify and wait for response.
        If succesful, session token will be stored in self.session_token
        :param factor: mfa information
        :type factor: dict
        :param state_token: token used in MFA back and forth
        :type: str
        :return: SUCCESS if push reported success.  INPUT_ERROR if user never responded.  Any other
        possibilities will result in an exception
        :rtype: OktaInitiator.Result
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
