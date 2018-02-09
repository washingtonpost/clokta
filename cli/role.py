'''
This is the entry-point to the cli application.
'''
import json
import logging
import os
import sys
from datetime import date, datetime

import boto3
import click
import requests
import yaml
from bs4 import BeautifulSoup

from cli.factor_chooser import FactorChooser
from cli.profile_manager import OutputFormat, ProfileManager
from cli.config_loader import ConfigLoader
from six.moves import input


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
        click.echo('Okta session token:')
        click.echo(session_token)

    saml_assertion = __saml_assertion_aws(
        session_token=session_token,
        configuration=configuration,
        verbose=verbose
    )
    if verbose:
        click.echo('SAML:')
        click.echo(saml_assertion)

    client = boto3.client('sts')
    response = client.assume_role_with_saml(
        RoleArn=configuration['OKTA_AWS_ROLE_TO_ASSUME'],
        PrincipalArn=configuration['OKTA_IDP_PROVIDER'],
        SAMLAssertion=saml_assertion
    )
    if verbose:
        click.echo('assume_role_with_saml:')
        click.echo(response)

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
        logging.exception(msg) if verbose else print(msg)
        sys.exit(1)
    except Exception as err:
        msg = 'Unexpected error: {}'.format(err)
        logging.exception(msg) if verbose else print(msg)
        sys.exit(1)

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
            logging.exception(msg) if verbose else print(msg)
            sys.exit(1)
    return okta_response['sessionToken']


def __okta_session_token_mfa(auth_response, factors, factor_preference, verbose=False):
    ''' Determine which factor to use and apply it to get a session token '''
    factor = __choose_factor(
        factors=factors,
        factor_preference=factor_preference,
        verbose=verbose
    )
    state_token = auth_response['stateToken']

    if factor['factorType'] == 'sms':
        __okta_mfa_verification(
            factor_dict=factor,
            state_token=state_token,
            otp_value=None
        )

    otp_value = input('Enter your multifactor authentication token: ')
    try:
        mfa_response = __okta_mfa_verification(
            factor_dict=factor,
            state_token=state_token,
            otp_value=otp_value
        )
        session_token = mfa_response['sessionToken']
    except requests.exceptions.HTTPError as http_err:
        msg = 'Okta returned this MFA related error: {}'.format(http_err)
        logging.exception(msg) if verbose else print(msg)
        sys.exit(1)
    except Exception as err:
        msg = 'Unexpected error: {}'.format(err)
        logging.exception(msg) if verbose else print(msg)
        sys.exit(1)

    return session_token


def __choose_factor(factors, factor_preference=None, verbose=False):
    ''' Automatically choose, or allow user to choose, the MFA option '''

    fc = FactorChooser(
        factors=factors,
        factor_preference=factor_preference,
        verbose=verbose
    )

    # Is there only one legitimate MFA option available?
    if len(factors) == 1:
        factor = fc.verify_only_factor(factor=factor)
        if factor:
            return factor

    # Has the user pre-selected a legitimate factor?
    if factor_preference:
        factor = fc.verify_preferred_factor()
        if factor:
            return factor

    return fc.choose_supported_factor()


def __okta_mfa_verification(factor_dict, state_token, otp_value=None):
    ''' Sends the  '''
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
        resp = json.loads(response.text)
        return resp
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
        with open('saml_response.html', 'wb') as f:
            f.write(response.content)

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
    else:
        response.raise_for_status()


def __write_aws_configs(role_credentials, output_format=OutputFormat.ShellScript, profile_name=None, verbose=False):
    ''' Generates a shell file you can execute to apply role credentials to the environment '''
    output_file_name = 'aws_session.sh'
    if verbose:
        print(json.dumps(
            obj=role_credentials,
            default=json_serial,
            indent=4,
            sort_keys=True
        ))

    if output_format == OutputFormat.ShellScript:
        lines = [
            'export AWS_ACCESS_KEY_ID={}\n'.format(
                role_credentials['Credentials']['AccessKeyId']
            ),
            'export AWS_SECRET_ACCESS_KEY={}\n'.format(
                role_credentials['Credentials']['SecretAccessKey']
            ),
            'export AWS_SESSION_TOKEN={}\n'.format(
                role_credentials['Credentials']['SessionToken']
            )
        ]
        with open(output_file_name, mode='w') as file_handle:
            file_handle.writelines(lines)
        print(
            "AWS keys saved to {loc}. To use, 'source {loc}'".format(
                loc=output_file_name
            )
        )

    if output_format == OutputFormat.Profile:
        # TODO: upsert credentials into the profile file
        pm = ProfileManager(profile_name=profile_name, verbose=verbose)
        pm.apply_credentials(role_credentials=role_credentials)
        

def json_serial(obj):
    ''' JSON serializer for objects not serializable by default json code '''
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
