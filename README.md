# Clokta: AWS CLI via Okta authentication

Clokta enables you authenticate into an AWS account using Okta on the command line, so that you can run AWS CLI commands.

## To Install

```bash
> pip3 install clokta
```

You will need Python 2.7 or 3 installed on your machine

## To Use

```
<<<<<<< HEAD
$ clokta --profile <your-team> -c <your-team-clokta-config>.yml
$ aws --profile <your-team> s3 ls (or any other aws command you want)
=======
> clokta --profile <your-team>
> aws --profile <your-team> s3 ls (or any other aws command you want)
>>>>>>> SEC-000-INIT
```

This injects temporary keys into your .aws/credentials file that can be accessed with the --profile option.

In addition, it creates a file which can be sourced to enable just the current session:

```
<<<<<<< HEAD
$ clokta -c <your-team-clokta-config>.yml
$ source aws_session.sh
$ aws s3 ls
=======
> clokta --profile <your-team>
> source ~/.clokta/<your team>.sh
> aws s3 ls
>>>>>>> SEC-000-INIT
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

<<<<<<< HEAD
1. Run AWS commands for the next hour.

  After an hour the keys expire and you must rerun clokta.

## Generating a clokta.yml for your team
=======
Run AWS commands for the next hour. After an hour the keys expire and you must rerun clokta.
>>>>>>> SEC-000-INIT

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

These are now all supported. For first-time usage, add `MULTIFACTOR_PREFERENCE` to the Okta config file but leave it blank, then press <return> when prompted by clokta. The tool will prompt from a set of options; copy/paste your preferred option (ex. `OKTA-sms`) into the config file to subsequently bypass this step.

### SEC-117

> Add '--profile/-p' option to CLI

When adding `--profile={name}` or `-p {name}` to the clokta command like, you instruct it to create a profile in the `~/.aws/credentials` file.

- if it exists already, the current version will be backed up to `~/.aws/credentials.bak`
  - none of the existing profiles will be lost
  - using the same name as an existing profile will overwrite its data
- if the credentials file doesn't exist, it will be created

### SEC-119

> Support Okta Verify with Push

If Okta Veridy push notifications are enabled, the option `Okta Verify with Push` will be available from the MFA selection prompt. Choosing this option will cause a push notification to be sent to your Okta Verify application.

The message `Push notification sent; waiting for your response` will appear, at which point clokta will poll every 3 seconds to determine if you have responded, up to a total of 60 seconds. Once clokta receives a confirmation of receipt, the message `Session confirmed` will print ut and the credentials will be stored.

To make this MFA mechanism the default, add this line to your clokta config file:

```yaml
MULTIFACTOR_PREFERENCE: Okta Verify with Push
```
