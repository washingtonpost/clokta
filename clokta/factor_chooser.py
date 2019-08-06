import click

from clokta.common import Common
from clokta.factors import Factors


class FactorChooser(object):
    """ Supports MFA source determination """

    def __init__(self, factors, factor_preference=None):
        """ Instance constructor """
        self.okta_factors = factors
        self.factor_preference = factor_preference

        self.cli_factors = self.__load_supported_factors()
        self.option_factors = self.__filter_unsupported_factors()

    def verify_only_factor(self, factor):
        """ Return the Okta MFA configuration provided it is a supported configuration """
        verified_factors = [
            opt for opt in self.option_factors
            if opt['provider'] == factor['provider'] and
            opt['factor_type'] == factor['factorType']
        ]
        if verified_factors:
            if Common.is_debug():
                msg = 'Using only available factor: {}'.format(verified_factors[0]['prompt'])
                Common.dump_out(message=msg)
            return factor

    def verify_preferred_factor(self):
        """ Return the Okta MFA configuration for the matching, supported configuration """
        preferred_factors = [
            opt for opt in self.option_factors
            if self.factor_preference == opt['prompt']
        ]
        if preferred_factors:
            if Common.is_debug():
                msg = 'Using preferred factor: {}'.format(self.factor_preference)
                Common.dump_out(message=msg)

            matching_okta_factor = [
                fact for fact in self.okta_factors
                if fact['provider'] == preferred_factors[0]['provider'] and
                fact['factorType'] == preferred_factors[0]['factor_type']
            ]

            return matching_okta_factor[0]

        else:
            msg = 'The MFA option \'{}\' in your configuration file is not available.\nAvailable options are {}'.format(
                self.factor_preference, [opt['prompt'] for opt in self.option_factors])
            Common.dump_err(message=msg)
            raise ValueError("Unexpected MFA option")  # TODO: Reprompt

    def choose_supported_factor(self):
        """ Give the user a choice from the intersection of configured and supported factors """
        index = 1
        for opt in self.option_factors:
            msg = '{index} - {prompt}'.format(index=index, prompt=opt['prompt'])
            Common.echo(message=msg, bold=True)
            index += 1

        raw_choice = None
        try:
            raw_choice = click.prompt('Choose a MFA type to use', type=int, err=Common.to_std_error())
            choice = raw_choice - 1
        except ValueError:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.choose_supported_factor()

        if len(self.option_factors) > choice >= 0:
            pass
        else:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.choose_supported_factor()

        chosen_option = self.option_factors[choice]
        matching_okta_factor = [
            fact for fact in self.okta_factors
            if fact['provider'] == chosen_option['provider'] and
            fact['factorType'] == chosen_option['factor_type']
        ]
        if Common.is_debug():
            Common.dump_out(message='Using chosen factor: {}'.format(chosen_option['prompt']))

        return matching_okta_factor[0]

    def __load_supported_factors(self):
        return Factors.mfa_providers()

    def __filter_unsupported_factors(self):
        factor_intersection = []
        for cli in self.cli_factors:
            for okta in self.okta_factors:
                if cli['provider'] == okta['provider'] and cli['factor_type'] == okta['factorType']:
                        factor_intersection.append(cli)
                        okta['clokta_id'] = cli['prompt']
        return factor_intersection
