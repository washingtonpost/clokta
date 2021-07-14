# Changelog

## v4.1.3
- Can now paste Okta URLs from Guidepost as well as Okta home page
- Okta now completely generic, no code is specific to Washington Post.  WashingtonPost-specific instructions have been moved out of the repo. 
- Fixed bug with not accepting URLs for non-Washington Post systems
- Fixed bug with running Okta when AWS_PROFILE is set to a non-existent profile

## v4.1.2
- Fixed error with older versions of click preinstalled

## v4.1.1
- Fixed error when password has been changed
- Fixed error OTP generation fails

## v4.1.0
- Saves password in keychain
- Can specify default role on command line
- Less verbose output with option for more verbose instructions
- Option to use inside eval commands
- Can list profiles available

## v4.0.1
- Generated shell script and docker files include setting the AWS_PROFILE variable

## v4.0
- Clokta only prompts you for your username and MFA the first time.  Subsequent calls within a 4 hour period will 
piggyback on the Okta session.

## v3.1.0

- Supports 1, 4, or 12 hour sessions.
- Better error messages
- --version command line flag

## v3.0.1

- Moved back to opensource development
- Better experience for first time users
 
## v2.0

- No longer creating temporary users.  Developer and Admins roles must have been manually configured for 12 hour sessions before hand.

## v1.0

- Now creates 12 hour sessions by creating a temporary IAM user
- Simplified clokta.cfg only needs Okta url.  Will prompt if no role ARN is provided

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
