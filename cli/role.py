'''
This is the entry-point to the cli application.
'''
import copy
import getpass
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

from six.moves import input


@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed .')
@click.option('--config', '-c', default=None, help='Path to configuration file.')
def assume_role(config=None, verbose=False):
    ''' entry point for the cli tool '''
    configuration = __load_configuration(config_path=config, verbose=verbose)
    if verbose:
        copy_config = copy.deepcopy(configuration)
        copy_config['OKTA_PASSWORD'] = '<redacted>'
        click.echo('Configuration:')
        click.echo(copy_config)

    session_token = __okta_session_token(configuration=configuration, verbose=verbose)
    if verbose:
        click.echo('Okta session token:')
        click.echo(session_token)

    saml_assertion = __saml_assertion_aws(session_token=session_token, configuration=configuration)
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

    __write_aws_configs(role_credentials=response, verbose=verbose)

def __load_configuration(config_path, verbose=False):
    ''' Configuration file values override environment variables '''
    cfg = {}
    configuration = {}
    if config_path:
        try:
            with open(config_path, 'r') as config_file:
                contents = config_file.read()
                cfg = yaml.load(contents, Loader=yaml.SafeLoader)
        except OSError as oserr:
            msg = 'Error related to your configuration file: {}'.format(oserr)
            logging.exception(msg) if verbose else print(msg)
            sys.exit(1)
        except Exception as err:
            msg = 'Unexpected error: {}'.format(err)
            logging.exception(msg) if verbose else print(msg)
            sys.exit(1)

    for key in [
            'OKTA_USERNAME',
            'OKTA_PASSWORD',
            'OKTA_ORG',
            'OKTA_AWS_APP_URL',
            'OKTA_AWS_ROLE_TO_ASSUME',
            'OKTA_IDP_PROVIDER',
            'MULTIFACTOR_PREFERENCE'
    ]:
        if key.endswith('PASSWORD'):
            configuration[key] = os.getenv(key, getpass.getpass(prompt="Enter a value for {}:".format(key)))
        else:
            configuration[key] = cfg.get(key) if cfg.get(key) \
                else os.getenv(key, input("Enter a value for {}:".format(key)))

    return configuration

def __okta_session_token(configuration, verbose=False):
    ''' Authenticate with Okta to create a session and receive a session token '''
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
        return __okta_session_token_mfa(
            auth_response=okta_response,
            factors=okta_response['_embedded']['factors'],
            factor_preference=configuration['MULTIFACTOR_PREFERENCE'],
            verbose=verbose
        )
    else:
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
        # TODO: ask for it to send us an MFA token
        send_sms_response = __okta_mfa_verification(
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
    if len(factors) == 1:
        if verbose:
            print('Using available factor: {}-{}'.format(
                factors[0]['provider'],
                factors[0]['factorType'],
            ))
        return factors[0]

    if factor_preference:
        matched_factors = [
            fact for fact in factors \
                if '{}-{}'.format(fact['provider'], fact['factorType']) == factor_preference
        ]
        if matched_factors:
            if verbose:
                print('Using preferred factor: {}'.format(factor_preference))
            return matched_factors[0]

    choice = 1
    index = 1
    for fact in factors:
        print(
            '{index} - {provider}-{factor_type}'.format(
                index=index,
                provider=fact['provider'],
                factor_type=fact['factorType']
            )
        )
        index += 1
    choice = int(input('Choose a MFA type to use:'))        
    return factors[choice - 1]

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
    if response.status_code == requests.codes.ok:
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
    if response.status_code == requests.codes.ok:
        resp = json.loads(response.text)
        return resp
    else:
        response.raise_for_status()

def __saml_assertion_aws(session_token, configuration):
    ''' fetch saml 2.0 assertion '''
    response = __okta_app_response(session_token=session_token, configuration=configuration)

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
    if response.status_code == requests.codes.ok:
        return response
    else:
        response.raise_for_status()

def __write_aws_configs(role_credentials, verbose=False):
    ''' Generates a shell file you can execute to apply role credentials to the environment '''
    output_file_name = 'aws_session.sh'
    if verbose:
        print(json.dumps(obj=role_credentials, default=json_serial, indent=4, sort_keys=True))

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

def json_serial(obj):
    ''' JSON serializer for objects not serializable by default json code '''
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
