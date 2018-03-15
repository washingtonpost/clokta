# Changelog

## v0.9

- support MFA via Okta Verify Push (where is pushes a notification to your phone and you just approve)
- -c command is removed.  All clokta configuration goes in a ~/.clokta/clokta.cfg and -p is used to select which one
- Clokta always puts keys in ~/.aws/credentials AND generates shell and env files in ~/.clokta/
- Now generates env files which can be used by docker-compose

## v0.8

- support for MFA via SMS and Okta Verify
- allows user to specify which MFA via MULTIFACTOR_PREFERENCE config option or will prompt user for which MFA to use
- --profile flag to inject keys into ~/.aws.credentials file

## v0.4

Supports Python 2.7 and 3.x

## v0.2

Initial public version