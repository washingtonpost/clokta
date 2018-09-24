# Clokta: AWS CLI via Okta authentication

Clokta enables you authenticate into an AWS account using Okta on the command line, so that you can run AWS CLI commands.

## To Install

You will need Python 2.7 or 3 installed on your machine.

Download the python package from

[https://github.com/WPMedia/clokta/archive/v2.0.tar.gz](https://github.com/WPMedia/clokta/archive/v2.0.tar.gz)

Install with

```
> sudo -H pip install -U clokta-2.0.tar.gz
```

if you are installing on a mac and encounter
```
Cannot uninstall 'six'. It is a distutils installed project and thus we cannot accurately determine which files belong to it which would lead to only a partial uninstall.
```
It's related to the System Integrity Protection software in the OS ( https://github.com/pypa/pip/issues/3165 ).. the following command should resolve the issue
```
sudo -H pip install --ignore-installed -U python-dateutil six
```


## To Use

```shell
> clokta --profile <your-team>
> aws --profile <your-team> s3 ls (or any other aws command you want)
```

This injects temporary keys into your .aws/credentials file that can be accessed with the --profile option.

In addition, it creates a file which can be sourced to enable just the current session:

```shell
> clokta --profile <your-team>
> source ~/.clokta/<your team>.sh
> aws s3 ls
```

Run AWS commands for the next 12 hours.  After 12 hours the keys expire and you must rerun clokta.

Applications that access AWS can be run locally if they used the second option that puts the keys in the environment of the current session.

**NOTE:** You will need a ~/.clokta/clokta.cfg file to specify your Okta setup.  Talk to you team about getting one or see below for generating a ~/.clokta/clokta.cfg

## More Info

Clokta will prompt you for a password and, if required, will prompt you for multi-factor authentication.  A typical scenario looks like

```shell
> clokta --profile meridian
Enter a value for okta_password:
1 - Google Authenticator
2 - Okta Verify
3 - SMS text message
4 - Okta Verify with Push
Choose a MFA type to use: 3
Enter your multifactor authentication token: 914345
AWS keys saved to ~/.clokta/meridian.sh. To use, `source ~/.clokta/meridian.sh`
AWS keys saved to ~/.clokta/meridian.env for use with docker compose
>
```

If you always intend on using the same the same MFA mechanism, you can put this in your clokta configuration file (see below).

### AWS Command Line, Local Programs, or Docker Containers

Clokta automatically inserts your credentials into ~/.aws/credentials using the '-p' name.  So you can immediately run aws commands with the '--profile' option.

```shell
> clokta -p meridian
> aws --profile meridian s3 ls
```

If you are developing applications that access AWS and need to run them locally, you can insert these credentials in your environment.  Clokta generates a shell script ~/.clokta/{profile}.sh for this.

```shell
> clokta -p meridian
> source ~/.clokta/meridian.sh
> ./bin/meridian
```

If you are building docker containers you can build them with the credentials in the environment using docker-compose's env_file command and referencing the {profile}.env file that clokta automatically creates.  A sample docker-compose.yml would like

```Yml
version: '2'
services:
  web:
    env_file:
      - ~/.clokta/meridian.env
    build: .
    ports:
     - "5000:5000"
    volumes:
     - .:/code
```

## Generating a ~/.clokta/clokta.cfg

The ~/.clokta/clokta.cfg will look like this.

```ini
[DEFAULT]
okta_username = doej
okta_org = washpost.okta.com
multifactor_preference = Okta Verify with Push

[meridian]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/0of1f11ff1fff1ffF1f1/272
```

### DEFAULT section

Specify your username, org and, if you want, specify which MFA option to use (valid options are 'Google Authenticator', 'Okta Verify with Push', 'SMS text message', and 'Okta Verify').  If you don't specify an MFA option it will prompt you.

### Profile sections

You will have a profile section for each team you work on (try to get the required information from your teammates instead of having to figure it out yourself).  

If no role is specified, as in the example clokta.cfg above, a user will be prompted for which role to assume.  As an alternative you can specify the role in the clokta.cfg or, as in the more realistic clokta.cfg below, you can specify two entries, one for the developer role and one for the admin role.

```ini
[DEFAULT]
okta_username = doej
okta_org = washpost.okta.com
multifactor_preference = Okta Verify with Push

[pagebuilder]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/0oe2e22ee2eee2eeE2e2/272

[meridian]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/0of1f11ff1fff1ffF1f1/272
okta_aws_role_to_assume = arn:aws:iam::111111111111:role/Okta_Developer_Access

[meridian-admin]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/0of1f11ff1fff1ffF1f1/272
okta_aws_role_to_assume = arn:aws:iam::111111111111:role/Okta_Admin_Access
```

To get the parameters `okta_aws_app_url` and `okta_aws_role_to_assume`, follow the below steps:

- okta_aws_app_url
  - Go to your Okta dashboard, right click on your AWS tile (e.g. ARC-App-Myapp), and copy the link.  It will be something like:
    `https://washpost.okta.com/home/amazon_aws/0oa1f77g6u1hoarrV0h8/272?fromHome=true`
  - Strip off the "?fromHome=true" and that is your okta_aws_app_url
- okta_aws_role_to_assume
  - Go to your AWS Account with the web console.
  - Click on IAM->Roles
  - Find and click the "Okta_Developer_Access" role
  - Copy the "Role Arn".  That is your okta_aws_role_to_assume

