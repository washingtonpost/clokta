# Clokta: AWS CLI via Okta authentication

Clokta enables you authenticate into an AWS account using Okta on the command line, so that you can run AWS CLI commands.

## To Install

```bash
> pip3 install clokta
```

You will need Python 2.7 or 3 installed on your machine

## To Use

```bash
> clokta -c <your-team-clokta-config>.yml
> source aws_session.sh
```

1. Ensure you have Google Authenticator setup in Okta.  Currently, Google Authenticator is the only MFA supported.

1. Obtain a clokta.yml from your team that contains the required information for you account.
   (See below for how a team can generate a clokta.yml)

   A typical clokta.yml will look like this.

```yaml
OKTA_ORG: washpost.okta.com
OKTA_AWS_APP_URL: https://washpost.okta.com/home/amazon_aws/0of1f11ff1fff1ffF1f1/272
OKTA_AWS_ROLE_TO_ASSUME: arn:aws:iam::111111111111:role/Okta_Role
OKTA_IDP_PROVIDER: arn:aws:iam::111111111111:saml-provider/Okta_Idp
OKTA_USERNAME:
MULTIFACTOR_PREFERENCE: OKTA-sms
```

Note: You can insert your username into the yml file or clokta will prompt you for it

Note: Alternatively, you can put all these values in your environment rather than specifying the yml file on the commandline.

1. Run AWS commands for the next hour.

   After an hour the keys expire and you must rerun clokta.

## Generating a clokta.yml for your team

Each team with its own account needs to setup a clokta.yml file for team member to use.  The clokta.yml contains all the Okta and AWS information clokta needs to find and authenticate with your AWS account.

Clokta needs the following information specific to your team AWS account:

- OKTA_ORG
  - This will always be 'washpost.okta.com'
- OKTA_AWS_APP_URL
  - Go to your Okta dashboard, right click on your AWS tile (e.g. ARC-App-Myapp), and copy the link.  It will be something like:
    `https://washpost.okta.com/home/amazon_aws/0oa1f77g6u1hoarrV0h8/272?fromHome=true`
  - Strip off the "?fromHome=true" and that is your OKTA_AWS_APP_URL
- OKTA_AWS_ROLE_TO_ASSUME
  - Go to your AWS Account with the web console.
  - Click on IAM->Roles
  - Find and click the "Okta_Developer_Access" role
  - Copy the "Role Arn".  That is your OKTA_AWS_ROLE_TO_ASSUME
- OKTA_IDP_PROVIDER
  - Go to your AWS Account with the web console.
  - Click on IAM->Identity providers
  - Find and click the "Washpost_Okta" provider
  - Copy the "Provider Arn".  That is your OKTA_IDP_PROVIDER

Create the file clokta.yml with the following information:

```yaml
OKTA_ORG: washpost.okta.com
OKTA_AWS_APP_URL: fill in value
OKTA_AWS_ROLE_TO_ASSUME: fill in value
OKTA_IDP_PROVIDER: fill in value
OKTA_USERNAME: fill in value
```

Note: The "OKTA_USERNAME" is just to make it easy for developers to put their name in when they get the file and not have to be prompted for it every time.  Leave it blank.

Give this to all team members.

## Recent updates

### SEC-115

> Extend duration of temp credentials 24 hours or as long as possible

According to [the boto3 documentation](http://boto3.readthedocs.io/en/latest/reference/services/sts.html#STS.Client.assume_role_with_saml):

<pre>
* DurationSeconds (integer) --
The duration, in seconds, of the role session. The value can range from 900 seconds (15 minutes) to 3600 seconds (1 hour). By default, the value is set to 3600 seconds. An expiration can also be specified in the SAML authentication response's SessionNotOnOrAfter value. The actual expiration time is whichever value is shorter.
</pre>

Given maximum value is also the default duration, the session must be re-freshed after 3600 seconds (1 hour).

### SEC-116

> Support other MFA options, SMS and Okta Verify

These are now all supported. For first-time usage, add `MULTIFACTOR_PREFERENCE` to the Okta config file but leave it blank, then press <return> when prompted by clokta. The tool will prompt from a set of options; copy/paste your preferred option (ex. `OKTA-sms`) into the config file to bypass that step.
