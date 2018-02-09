''' ProfileManager class must be instantiated prior to use. '''
import configparser
import enum
import os


class OutputFormat(enum.Enum):
    ''' Enumeration for credentials output format codes '''
    ShellScript = 'SHELL'
    Profile = 'PROFILE'


class ProfileManager(object):
    ''' Supports profile file management '''

    def __init__(self, profile_name, profiles_location='~/.aws/credentials', verbose=False):
        ''' Instance constructor '''
        self.profile_name = profile_name
        self.profiles_location = os.path.expanduser(profiles_location)
        self.verbose = verbose

        self.profiles_backup_location = os.path.expanduser(
            '{}.bak'.format(
                self.profiles_location
            )
        )

    def apply_credentials(self, role_credentials):
        ''' Save a set of temporary credentials '''
        self.__backup_profiles()

        config = configparser.ConfigParser()
        config.read(self.profiles_location)

        if self.profile_name not in config.sections():
            if self.verbose:
                print('Adding profile section', self.profile_name)
            config.add_section(self.profile_name)

        config.set(
            section=self.profile_name,
            option='AWS_ACCESS_KEY_ID',
            value=role_credentials['Credentials']['AccessKeyId']
        )
        config.set(
            section=self.profile_name,
            option='AWS_SECRET_ACCESS_KEY',
            value=role_credentials['Credentials']['SecretAccessKey']
        )
        config.set(
            section=self.profile_name,
            option='AWS_SESSION_TOKEN',
            value=role_credentials['Credentials']['SessionToken']
        )

        if self.verbose:
            print('Re-writing credentials file', self.profiles_location)

        if not os.path.exists(os.path.dirname(self.profiles_location)):
            os.makedirs(os.path.dirname(self.profiles_location))

        with open(self.profiles_location, 'w') as configfile:
            config.write(configfile)

    def __backup_profiles(self):
        if os.path.isfile(path=self.profiles_location):
            with open(self.profiles_location, 'r') as profile_file:
                contents = profile_file.read()

            with open(self.profiles_backup_location, 'w') as bak_file:
                bak_file.write(contents)
