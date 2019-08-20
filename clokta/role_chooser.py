
''' RoleChooser class must be instantiated prior to use '''

import click

from clokta.common import Common


class RoleChooser(object):
    """
    Supports AWS Role determination
    """

    def __init__(self, possible_roles, role_preference=None):
        """
        :param possible_roles: list of possible roles to choose from
        :type possible_roles: List[AwsRole]
        :param role_preference: preferred role
        :type role_preference: str
        """
        self.possible_roles = possible_roles
        self.role_preference = role_preference

    def choose_role(self):
        """
        Look for a default role defined and, if not, prompt the user for one
        Allow the user to also specify the role is the default to be used
        from now on
        :return: a tuple of the chosen role and whether it is the
        new default
        :rtype: AwsRole, bool
        """
        # throw an error if no roles are provided
        #  (defensive coding only - this should not be possible)
        if not self.possible_roles:
            Common.dump_err(
                message='No AWS Role was assigned to this application!'
            )
            raise ValueError('Unexpected configuration - No AWS role assigned to Okta login.')

        # use the one provided if there is only one
        if len(self.possible_roles) == 1:
            role = self.possible_roles[0]
            if self.role_preference and role.role_arn != self.role_preference:
                Common.dump_err(
                    message='Your cofigured role "{notfound}" was not found; using "{found}" role'.format(
                        notfound=self.role_preference,
                        found=role.role_name
                    )
                )
            elif Common.is_debug():
                Common.echo(
                    message="Using default role '{role}'".format(
                        role=role.role_arn
                    )
                )
            return role, False

        # use the configured role if it matches one from the the SAML assertion
        for role in self.possible_roles:
            if role.role_arn == self.role_preference:
                message = "Using default role '{}'".format(role.role_name)
                extra_message = '.  Run "clokta --no-default-role" to override.'
                if Common.get_output_format() == Common.long_out:
                    Common.echo(message + extra_message)
                else:
                    Common.echo(message)
                return role, True

        # make the user choose
        return self.__prompt_for_role(with_set_default_option=True)

    def __prompt_for_role(self, with_set_default_option):
        """
        Give the user a choice from the intersection of configured and supported factors
        :param with_set_default_option: if True will add an option for setting a default role
        :type with_set_default_option: bool
        :return: a tuple of what role was chosen and whether it is the new default
        :rtype: AwsRole, bool
        """
        index = 1
        for role in self.possible_roles:
            msg = '{index} - {prompt}'.format(
                index=index,
                prompt=role.role_name
            )
            Common.echo(message=msg, bold=True)
            index += 1
        if with_set_default_option:
            Common.echo('{index} - set a default role'.format(index=index))
        raw_choice = None
        try:
            raw_choice = click.prompt(text='Choose a Role ARN to use', type=int, err=Common.to_std_error())
            choice = raw_choice - 1
        except ValueError:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.__prompt_for_role()

        if choice == len(self.possible_roles):
            # They want to set a default.  Prompt again (just without the set-default option)
            # and return that chosen role and that it's the new default
            chosen_option, _ = self.__prompt_for_role(with_set_default_option=False)
            return chosen_option, True
        if len(self.possible_roles) > choice >= 0:
            pass
        else:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.__prompt_for_role(with_set_default_option=with_set_default_option)

        chosen_option = self.possible_roles[choice]
        if Common.is_debug():
            Common.dump_out(
                message='Using chosen Role {role} & IDP {idp}'.format(
                    role=chosen_option.role_arn,
                    idp=chosen_option.idp_arn
                )
            )

        return chosen_option, False
