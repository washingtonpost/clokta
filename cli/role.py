'''
This is the entry-point to the cli application.
'''
import json

import boto3
import click
import requests
import time
from bs4 import BeautifulSoup

from cli.common import Common
from cli.config_loader import ConfigLoader
from cli.factor_chooser import FactorChooser
from cli.profile_manager import OutputFormat, ProfileManager


@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed')
@click.option('--config', '-c', default=None, help='Path to configuration file')
@click.option('--profile', '-p', default=None, help='Profile to save to')
def assume_role(config=None, profile=None, verbose=False):
    ''' entry point for the cli tool '''
    configuration = ConfigLoader.load_configuration(config_path=config, verbose=verbose)

    session_token = __okta_session_token(
        configuration=configuration,
        verbose=verbose
    )
    if verbose:
        Common.dump_verbose(message='Okta session token: {}'.format(session_token))

    saml_assertion = __saml_assertion_aws(
        session_token=session_token,
        configuration=configuration,
        verbose=verbose
    )
    client = boto3.client('sts')
    response = client.assume_role_with_saml(
        RoleArn=configuration['OKTA_AWS_ROLE_TO_ASSUME'],
        PrincipalArn=configuration['OKTA_IDP_PROVIDER'],
        SAMLAssertion=saml_assertion
    )
    __write_aws_configs(
        role_credentials=response,
        output_format=OutputFormat.Profile if profile else OutputFormat.ShellScript,
        profile_name=profile,
        verbose=verbose
    )


def __okta_session_token(configuration, verbose=False):
    ''' Authenticate with Okta; receive a session token '''
    okta_response = None

    try:
        okta_response = __okta_auth_response(configuration=configuration)
    except requests.exceptions.HTTPError as http_err:
        msg = 'Okta returned this credentials/password related error: {}'.format(http_err)
        Common.dump_err(message=msg, exit_code=1, verbose=verbose)
    except Exception as err:
        msg = 'Unexpected error: {}'.format(err)
        Common.dump_err(message=msg, exit_code=2, verbose=verbose)

    # handle case where MFA is required but no factors have been enabled
    if okta_response['status'] == 'MFA_ENROLL':
        msg = 'Please enroll in multi-factor authentication before using this tool'
        Common.dump_err(message=msg, exit_code=3, verbose=verbose)

    if okta_response['status'] == 'MFA_REQUIRED':
        factors = okta_response['_embedded']['factors']
        if factors:
            return __okta_session_token_mfa(
                auth_response=okta_response,
                factors=factors,
                factor_preference=configuration['MULTIFACTOR_PREFERENCE'],
                verbose=verbose
            )
        else:
            msg = 'No MFA factors have been set up for this account'
            Common.dump_err(message=msg, exit_code=3, verbose=verbose)

    return okta_response['sessionToken']


def __okta_session_token_mfa(auth_response, factors, factor_preference, verbose=False):
    ''' Determine which factor to use and apply it to get a session token '''
    factor = __choose_factor(
        factors=factors,
        factor_preference=factor_preference,
        verbose=verbose
    )
    state_token = auth_response['stateToken']

    if factor['factorType'] == 'push':
        return __send_push(
            factor=factor,
            state_token=state_token
        )

    if factor['factorType'] == 'sms':
        __okta_mfa_verification(
            factor_dict=factor,
            state_token=state_token,
            otp_value=None
        )

    otp_value = click.prompt('Enter your multifactor authentication token', type=str)
    try:
        mfa_response = __okta_mfa_verification(
            factor_dict=factor,
            state_token=state_token,
            otp_value=otp_value
        )
        session_token = mfa_response['sessionToken']
    except requests.exceptions.HTTPError as http_err:
        msg = 'Okta returned this MFA related error: {}'.format(http_err)
        Common.dump_err(message=msg, exit_code=1, verbose=verbose)
    except Exception as err:
        msg = 'Unexpected error: {}'.format(err)
        Common.dump_err(message=msg, exit_code=2, verbose=verbose)

    return session_token


def __send_push(factor, state_token):
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
            return __check_push_result(
                state_token=state_token,
                push_response=response_data
            )


def __check_push_result(state_token, push_response):
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
            Common.echo(message='Session confirmed')
            break
        time.sleep(3)

    if response_data:
        return response_data['sessionToken']
    else:
        msg = 'Timeout expired ({} seconds)'.format(wait_for)
        Common.dump_err(message=msg, exit_code=3)


def __choose_factor(factors, factor_preference=None, verbose=False):
    ''' Automatically choose, or allow user to choose, the MFA option '''

    fact_chooser = FactorChooser(
        factors=factors,
        factor_preference=factor_preference,
        verbose=verbose
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


def __okta_mfa_verification(factor_dict, state_token, otp_value=None):
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


def __okta_auth_response(configuration):
    ''' Returns an HTTP response for credentials-based authentication with Okta '''
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Cache-Control': '"no-cache'
    }
    payload = {
        'username': configuration['OKTA_USERNAME'],
        'password': configuration['OKTA_PASSWORD']
    }
    url = 'https://' + configuration['OKTA_ORG'] + '/api/v1/authn'

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    if response.status_code == requests.codes.ok:  # pylint: disable=E1101
        resp = json.loads(response.text)
        return resp
    else:
        response.raise_for_status()


def __saml_assertion_aws(session_token, configuration, verbose=False):
    ''' fetch saml 2.0 assertion '''
    response = __okta_app_response(session_token=session_token, configuration=configuration)

    if verbose:
        with open('saml_response.html', 'wb') as file_handle:
            file_handle.write(response.content)

    soup = BeautifulSoup(response.content, "html.parser")
    assertion = None
    for inputtag in soup.find_all('input'):
        if inputtag.get('name') == 'SAMLResponse':
            assertion = inputtag.get('value')
    return assertion


def __okta_app_response(session_token, configuration):
    url = configuration['OKTA_AWS_APP_URL'] + '?onetimetoken=' + session_token
    response = requests.get(url)
    if response.status_code == requests.codes.ok:  # pylint: disable=E1101
        return response
    response.raise_for_status()


def __write_aws_configs(role_credentials, output_format=OutputFormat.ShellScript, profile_name=None, verbose=False):
    ''' Generates a shell file you can execute to apply role credentials to the environment '''
    output_file_name = 'aws_session.sh'
    if verbose:
        msg = json.dumps(obj=role_credentials, default=Common.json_serial, indent=4)
        Common.dump_verbose(message=msg)

    if output_format == OutputFormat.ShellScript:
        root = role_credentials['Credentials']
        lines = [
            'export AWS_ACCESS_KEY_ID={}\n'.format(root['AccessKeyId']),
            'export AWS_SECRET_ACCESS_KEY={}\n'.format(root['SecretAccessKey']),
            'export AWS_SESSION_TOKEN={}\n'.format(root['SessionToken'])
        ]
        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)

        msg = 'AWS keys saved to {loc}. To use, `source {loc}`'.format(
            loc=output_file_name
        )
        Common.echo(message=msg)

    if output_format == OutputFormat.Profile:
        profile_mgr = ProfileManager(profile_name=profile_name, verbose=verbose)
        profile_mgr.apply_credentials(role_credentials=role_credentials)
