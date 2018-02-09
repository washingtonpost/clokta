''' ProfileManager class must be instantiated prior to use '''
import yaml

class FactorChooser(object):
    ''' Supports MFA source determination '''

    def __init__(self, factors, factor_preference=None, verbose=False):
        ''' Instance constructor '''
        self.okta_factors = factors
        self.factor_preference = factor_preference
        self.verbose = verbose

        self.cli_factors = self.__load_supported_factors()
        self.option_factors = self.__filter_unsupported_factors()

    def verify_only_factor(self, factor):
        ''' Return the Okta MFA configuration provided it is a supported configuration '''
        verified_factors = [
            opt for opt in self.option_factors
            if opt['provider'] == factor['provider'] and
            opt['factor_type'] == factor['factorType']
        ]
        if verified_factors:
            if self.verbose:
                print('Using only available factor:', verified_factors[0]['prompt'])
            return factor

    def verify_preferred_factor(self):
        ''' Return the Okta MFA configuration for the matching, supported configuration '''
        preferred_factors = [
            opt for opt in self.option_factors
            if self.factor_preference == opt['prompt']
        ]
        if preferred_factors:
            if self.verbose:
                print('Using preferred factor:', self.factor_preference)

            matching_okta_factor = [
                fact for fact in self.okta_factors
                if fact['provider'] == preferred_factors[0]['provider'] and
                fact['factorType'] == preferred_factors[0]['factor_type']
            ]

            return matching_okta_factor[0]
            
        else:
            print(
                'The MFA option in your configuration file is not available.',
                'Check with your Okta configuration to ensure it is configured and enabled.'
            )

    def choose_supported_factor(self):
        ''' Give the user a choice from the intersection of configured and supported factors '''
        index = 1
        for opt in self.option_factors:
            print(
                '{index} - {prompt}'.format(
                    index=index,
                    prompt=opt['prompt']
                )
            )
            index += 1

        raw_choice = None
        try:
            raw_choice = input('Choose a MFA type to use:')
            choice = int(raw_choice) - 1
        except ValueError as err:
            print('Please select a valid option: you chose', raw_choice)
            return self.choose_supported_factor()

        if len(self.option_factors) > choice >= 0:
            pass
        else:
            print('Please select a valid option: you chose', raw_choice)
            return self.choose_supported_factor()

        chosen_option = self.option_factors[choice]
        matching_okta_factor = [
            fact for fact in self.okta_factors
            if fact['provider'] == chosen_option['provider'] and
            fact['factorType'] == chosen_option['factor_type']
        ]
        if self.verbose:
            print('Using chosen factor:', chosen_option['prompt'])

        return matching_okta_factor[0]

    def __load_supported_factors(self):
        with open('cli/factors.yml', 'r') as factors_file:
            contents = factors_file.read()
            cli_supported_factors = yaml.load(contents, Loader=yaml.SafeLoader)['MfaProviders']

        return cli_supported_factors

    def __filter_unsupported_factors(self):
        factor_intersection = []
        for cli in self.cli_factors:
            for okta in self.okta_factors:
                if cli['provider'] == okta['provider'] and \
                cli['factor_type'] == okta['factorType']:
                    factor_intersection.append(cli)

        return factor_intersection
