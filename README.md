# Clokta: AWS CLI via Okta authentication

Clokta enables you authenticate into an AWS account using Okta on the command line, so that you can run AWS CLI commands.

## To Install

```bash
> pip3 install clokta
```

You will need Python 2.7 or 3 installed on your machine

## To Use

```
> clokta --profile <your-team>
> aws --profile <your-team> s3 ls (or any other aws command you want)
```

This injects temporary keys into your .aws/credentials file that can be accessed with the --profile option.

In addition, it creates a file which can be sourced to enable just the current session:

```
> clokta --profile <your-team>
> source ~/.clokta/<your team>.sh
> aws s3 ls
```

Run AWS commands for the next hour.  After an hour the keys expire and you must rerun clokta.

Applications that access AWS can be run locally if the you used the second option that puts the keys in the environment of the current session.

Obtain a clokta.cfg from your team.   See below for how a team can generate a clokta.cfg.

## More Info

Clokta will prompt you for a password and, if required, will prompt you for multi-factor authentication.  A typical scenario looks like

```shell
> clokta --profile meridian
Enter a value for okta_password:
1 - Google Authenticator
2 - Okta Verify
3 - SMS text message
Choose a MFA type to use: 3
Enter your multifactor authentication token: 914345
>
```

If you always intend on using the same the same MFA mechanism, you can put this in your clokta configuration file. For example, the line "multifactor_preference: SMS text message" will always use SMS MFA.

The ~/.clokta/clokta.cfg will look like this. The [DEFAULT] section will be mixed with the <your-team> section so you don't have to repeat it in each configuration profile.

```ini
[DEFAULT]
okta_username =
okta_org = washpost.okta.com
multifactor_preference =

[<your team>]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/0of1f11ff1fff1ffF1f1/272
okta_aws_role_to_assume = arn:aws:iam::111111111111:role/Okta_Role
okta_idp_provider = arn:aws:iam::111111111111:saml-provider/Okta_Idp
```

Note: You can insert your username or preferred multifactor mechanism into the config or clokta will prompt you for them.

Note: Alternatively, you can put all these values in your environment rather than specifying the yml file on the commandline.

Run AWS commands for the next hour. After an hour the keys expire and you must rerun clokta.

## Generating a clokta.cfg for your team

Each team with its own account needs to setup a clokta.cfg file for team member to use; it contains all the Okta and AWS information clokta needs to find and authenticate with your AWS account.

Clokta needs the following information specific to your team AWS account:

- okta_org
  - This will always be 'washpost.okta.com'
- okta_aws_app_url
  - Go to your Okta dashboard, right click on your AWS tile (e.g. ARC-App-Myapp), and copy the link.  It will be something like:
    `https://washpost.okta.com/home/amazon_aws/0oa1f77g6u1hoarrV0h8/272?fromHome=true`
  - Strip off the "?fromHome=true" and that is your okta_aws_app_url
- okta_aws_role_to_assume
  - Go to your AWS Account with the web console.
  - Click on IAM->Roles
  - Find and click the "Okta_Developer_Access" role
  - Copy the "Role Arn".  That is your okta_aws_role_to_assume
- okta_idp_provider
  - Go to your AWS Account with the web console.
  - Click on IAM->Identity providers
  - Find and click the "Washpost_Okta" provider
  - Copy the "Provider Arn".  That is your okta_idp_provider

Create the file clokta.cfg with the following information:

```ini
[DEFAULT]
okta_username =
okta_org = washpost.okta.com
multifactor_preference =

[<your team>]
okta_aws_app_url = fill in value
okta_aws_role_to_assume = fill in value
okta_idp_provider = fill in value
```

Note: The "okta_username" is just to make it easy for developers to put their name in when they get the file and not have to be prompted for it every time.  Leave it blank.

Give this to all team members.
