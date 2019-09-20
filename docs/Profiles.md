# Clokta: Understanding Profiles

Profiles is an extension of the AWS CLI/API way of handling more than one set of credentials.

While AWS supports "federated" logins such as Okta, it does so by providing a service/endpoint that allows you to exchange your federated credentials for a session token which the AWS API will recognize. 

## AWS API/CLI "Profiles"

[AWS Configuring the CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

Initially you are instructed to run "aws configure" which then asks you for 4 pieces of information:
```
$ aws configure
AWS Access Key ID [None]: MyAccessKey
AWS Secret Access Key [None]: MySecretKey
Default region name [None]: us-east-2
Default output format [None]: text
```

As a result of the above action the following data is configured into 2 files which AWS uses for providing your credentials

```
$ cat ~/.aws/config 
[default]
region = us-east-2
output = text

$ cat ~/.aws/credentials
[default]
aws_access_key_id = MyAccessKey
aws_secret_access_key = MySecretKey
```

Optionally you can specify a different set of credentials (maybe another account, maybe just different IAM role in the same account)

```
$ aws configure --profile MyAdminRole
AWS Access Key ID [None]: MyAdminAccessKey
AWS Secret Access Key [None]: MyAdminSecret
Default region name [None]: us-west-1
Default output format [None]: json
```

and if we look at the two files, as expected

```
$ cat ~/.aws/config 
[default]
region = us-east-2
output = text
[profile MyAdminRole]
region = us-west-1
output = json

$ cat ~/.aws/credentials 
[default]
aws_access_key_id = MyAccessKey
aws_secret_access_key = MySecretKey
[MyAdminRole]
aws_access_key_id = MyAdminAccessKey
aws_secret_access_key = MyAdminSecret
```

## Clokta "Profiles"

For the same reason the AWS API supports more than one set of credentials, so clokta supports the concept of profiles and makes use of the "Clokta" profile name as the "AWS" profile name for simplicity.

```
$ clokta -p MyAdminRole
No profile "MyAdminRole" in clokta.cfg, but enter the information and clokta will create a profile.
Copy the link from the Okta App: https://washpost.okta.com/home/amazon_aws/0oaXXXXXXXXXXRv0h8/272?fromHome=true
Enter a value for okta_password: XXXXXXXXXXXX
Enter your multifactor authentication token: XXXXXX
Using the configured role arn:aws:iam::041979207332:role/Okta_Developer_Access
AWS keys generated. To use, run "export AWS_PROFILE=MyAdminRole"
or use files ~/.clokta/MyAdminRole.env with docker compose or ~/.clokta/MyAdminRole.sh with shell scripts
```

In the above example I used the same "MyAdminRole" profile as I had used in the example above, it will "update" the section in the ~/.aws/credentials file with the data created by the exchange of the "Okta" token for AWS tokens. Side note, credentials obtained through a "federated" login such as Okta are time limited and as such also have a "session token" which is the extra line inserted into the MyAdminRole profile. 

```
$ cat ~/.aws/credentials 
[default]
aws_access_key_id = MyAccessKey
aws_secret_access_key = MySecretKey

[MyAdminRole]
aws_access_key_id = ASIAQXXXXXXSJOLVMAH3
aws_secret_access_key = L3PSgJXXXXXXXXXXXXXXXXXXXXXXXXXXDZY7gwtx
aws_session_token = FQoGZXIvYXdzEKH//////////wEaDF+BL08XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXfVZwMjuhH3K/hNUgX7ncoWV33kS4Q1VXY/akzx29ryvbbLLW0omZl41uPSeKaM3KcBpOlWGdDFMJVxqfP6rViH2+6YdhdFkspPgE26JIScF+MBNLfAhW7jTUEqxvre3VmybNn5Rdm2PxiVoblXXXXXXXXXXXXXXXXXXXXXHZ0a4pjc4AQByHIbO8wJ/5RIoe8Ifw2oy+HsbZMyrPGGg6eHgFXXXXXXXXXXXXXXXXXXXXCNwseY19/GgUOyWA+JGEuMZZPWuG23xxGWjhJNOUN3FsZtIv5D4yWNMCOWsB6kwIerQ4K7tk3+wPQ1ZFvFmn3Mb6Tr5FNCiynfPoBQ==
```

In addition to the AWS files stored in the users home directory, Clokta stores two files in the users home as well

```
$ cat ~/.clokta/clokta.cfg
[DEFAULT]
okta_org = washpost.okta.com
okta_username = almr
multifactor_preference = Google Authenticator

[MyAdminRole]
okta_aws_app_url = https://washpost.okta.com/home/amazon_aws/XXXXXXXXXXXXXXXXXXXX/272
```

## Clokta "default" profile

Since the AWS API/CLI allows for a profile named "default", creating a clokta profile named "default" works well for users which only have a single Okta profile or those who spend a significant amount of time using a single profile.

`clokta -p default` will create a profile named [default] which will result in the [default] profile being created in the AWS config files.
