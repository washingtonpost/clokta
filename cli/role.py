'''
This is the entry-point to the cli application.
'''
import copy
import getpass
import json
import os
import sys
from datetime import date, datetime

import boto3
import requests

import click
import yaml
from bs4 import BeautifulSoup
from six.moves import input


@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed .')
@click.option('--config', '-c', default=None, help='Path to configuration file.')
def assume_role(config=None, verbose=False):
    configuration = load_configuration(config_path=config, verbose=verbose)
    if verbose == True:
        copy_config = copy.deepcopy(configuration)
        copy_config['OKTA_PASSWORD'] = '<redacted>'
        click.echo('Configuration:')
        click.echo(copy_config)

    session_token = okta_session_token(configuration=configuration)
    if verbose == True:
        click.echo('Okta session token:')
        click.echo(session_token)

    saml_assertion = saml_assertion_aws(session_token=session_token, configuration=configuration)
    if verbose == True:
        click.echo('SAML:')
        click.echo(saml_assertion)

    client = boto3.client('sts')
    response = client.assume_role_with_saml(
        RoleArn=configuration['OKTA_AWS_ROLE_TO_ASSUME'],
        PrincipalArn=configuration['OKTA_IDP_PROVIDER'],
        SAMLAssertion=saml_assertion
    )
    if verbose == True:
        click.echo('assume_role_with_saml:')
        click.echo(response)

    write_aws_configs(role_credentials=response, verbose=verbose)

def load_configuration(config_path, verbose=False):
    ''' Configuration file values override environment variables '''
    cfg = {}
    configuration = {}
    if config_path:
        if not os.path.isfile(config_path):
            raise ValueError("No such file '{}'".format(config_path))            
        else:
            with open(config_path, 'r') as config_file:
                contents = config_file.read()
                cfg = yaml.load(contents, Loader=yaml.SafeLoader)

    for key in [
            'OKTA_USERNAME', 'OKTA_PASSWORD', 'OKTA_ORG', 'OKTA_AWS_APP_URL', 'OKTA_AWS_ROLE_TO_ASSUME', 'OKTA_IDP_PROVIDER'
    ]:
        if key.endswith('PASSWORD'):
            configuration[key] = cfg.get(key) if cfg.get(key) else os.getenv(key, getpass.getpass(prompt="Enter a value for {}:".format(key)))
        else:
            configuration[key] = cfg.get(key) if cfg.get(key) else os.getenv(key, input("Enter a value for {}:".format(key)))

    return configuration

def okta_session_token(configuration):
    session_token = None
    okta_response = None

    try:
        okta_response = okta_auth_response(configuration=configuration)
    except requests.exceptions.HTTPError as err:
        print('Okta returned this credentials/password related error: {}'.format(err))
        exit(1)
    except:
        print("Unexpected error:", sys.exc_info()[0])
        exit(1)

    if okta_response['status'] == 'MFA_REQUIRED':
        # TODO: query user for MFA token, re-validate session token
        factors = [
            fact for fact in okta_response['_embedded']['factors'] if fact['factorType'] == 'token:software:totp' and fact['provider'] == 'GOOGLE'
        ]
        if factors:
            factor = factors[0]
            state_token = okta_response['stateToken']
            otp_value = input("Enter your Google Authenticator token:")
            try:
                mfa_response = okta_mfa_verification(
                    factor_dict= factor,
                    state_token=state_token,
                    otp_value=otp_value
                )
                session_token = mfa_response['sessionToken']
            except requests.exceptions.HTTPError as err:
                print('Okta returned this MFA related error: {}'.format(err))
                exit(1)
            except:
                print("Unexpected error:", sys.exc_info()[0])
                exit(1)
    else:
        session_token = okta_response['sessionToken']

    return session_token

def okta_mfa_verification(factor_dict, state_token, otp_value):
    url = factor_dict['_links']['verify']['href']
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Cache-Control': '"no-cache'
    }
    payload = {
        'stateToken': state_token,
        'answer': otp_value
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers)
    if response.status_code == requests.codes.ok:
        resp = json.loads(response.text)
        return resp
    else:
        response.raise_for_status()

def okta_auth_response(configuration):
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

def saml_assertion_aws(session_token, configuration):
    response = okta_app_response(session_token=session_token, configuration=configuration)
    # with open('saml_response.html', 'wb') as f:
    #     f.write(response.content)
    soup = BeautifulSoup(response.content, "html.parser")
    assertion = None 
    for inputtag in soup.find_all('input'):
        if(inputtag.get('name') == 'SAMLResponse'):
            assertion = inputtag.get('value')
    return assertion

def okta_app_response(session_token, configuration):
    url = configuration['OKTA_AWS_APP_URL'] + '?onetimetoken=' + session_token
    response = requests.get(url)
    if response.status_code == requests.codes.ok:
        return response
    else:
        response.raise_for_status()

def write_aws_configs(role_credentials, verbose=False):
    output_file_name = 'aws_session.sh'
    if verbose == True:
        print(json.dumps(obj=role_credentials, default=json_serial, indent=4, sort_keys=True))

    lines = [
        'export AWS_ACCESS_KEY_ID={}\n'.format(role_credentials['Credentials']['AccessKeyId']),
        'export AWS_SECRET_ACCESS_KEY={}\n'.format(role_credentials['Credentials']['SecretAccessKey']),
        'export AWS_SESSION_TOKEN={}\n'.format(role_credentials['Credentials']['SessionToken'])
    ]
    with open(output_file_name, mode='w') as f:
        f.writelines(lines)
    print(
        "AWS keys saved to {loc}. To use, 'source {loc}'".format(
            loc=output_file_name
        )
    )

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
