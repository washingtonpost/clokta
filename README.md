# Clokta: AWS CLI via Okta authentication

Clokta enables you authenticate into an AWS account using Okta on the command line, so that you can run AWS CLI commands.

## To Install

1. Ensure you have Python3 on your machine

2. Clone the clokta repo, https://github.com/WPMedia/clokta

3. From the clokta/ directory, run:

   ```bash
   python3 -m venv .env
   . .env/bin/activate
   pip3 install -e .
   ```

4. Add clokta to your path, either by putting `«path_to_clokta»/.env/bin` in your PATH or creating a soft link to  `«path_to_clokta»/.env/bin/clokta` in a directory that is already in your path

## To Use

1. Ensure you have Google Authenticator setup in Okta.  Currently, Google Authenticator is the only MFA supported.

2. Obtain a clokta.yml from your team that contains the required information for you account.
   (See below for how a team can generate a clokta.yml)

   A typical clokta.yml will look like this.

```yaml
OKTA_ORG: washpost.okta.com
OKTA_AWS_APP_URL: https://washpost.okta.com/home/amazon_aws/0oa1f77af1aee9wnX0h8/272
OKTA_AWS_ROLE_TO_ASSUME: arn:aws:iam::542114373238:role/Okta_Developer_Access
OKTA_IDP_PROVIDER: arn:aws:iam::542114373238:saml-provider/Washpost_Okta
OKTA_USERNAME:
```

Note: You can insert your username into the yml file or clokta will prompt you for it

Note: Alternatively, you can put all these values in your environment rather than specifying the yml file on the commandline.

3. Run `clokta -c clokta.yml` and `source aws_session.sh`

   ```
   > clokta -c clokta.yml
   Enter a value for OKTA_USERNAME: doej
   Enter a value for OKTA_PASSWORD: ********
   Enter your Google Authenticator token: 456748
   AWS keys saved to aws_session.sh.  To use, 'source aws_session.sh'
   > source aws_sesion.sh
   > aws s3api list-buckets
   ...
   ```

4. Run AWS commands for the next hour.  
   After an hour the keys expire and you must rerun clokta.

## Generating a clokta.yml for your team

Each team with its own account needs to setup a clokta.yml file for team member to use.  The clokta.yml contains all the Okta and AWS information clokta needs to find and authenticate with your AWS account.

Clokta needs the following information specific to your team AWS account:

- OKTA_ORG
  - This will always be 'washpost.okta.com'
- OKTA_AWS_APP_URL
  - Go to your Okta dashboard, right click on your AWS tile (e.g. ARC-App-Myapp), and copy the link.  It will be something like:
    https://washpost.okta.com/home/amazon_aws/0oa1f77g6u1hoarrV0h8/272?fromHome=true
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
OKTA_USERNAME:
```

Note: The "OKTA_USERNAME" is just to make it easy for developers to put their name in when they get the file and not have to be prompted for it every time.  Leave it blank.

Give this to all team members.
