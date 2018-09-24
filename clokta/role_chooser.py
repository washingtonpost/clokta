
''' RoleChooser class must be instantiated prior to use '''
import base64
import xml.etree.ElementTree as ET

import click

from clokta.common import Common
from clokta.factors import Factors


class RoleChooser(object):
    ''' Supports AWS Role determination '''

    def __init__(self, saml_assertion, role_preference=None, verbose=False):
        ''' Instance constructor '''
        self.saml_assertion = saml_assertion
        self.role_preference = role_preference
        self.verbose = verbose

    def choose_idp_role_tuple(self):
        ''' Determine the role options the user can choose from '''
        idp_role_tuples = self.__discover_role_idp_tuples()

        # throw an error if no roles are provided
        #  (defensive coding only - this should not be impossible)
        if not idp_role_tuples:
            Common.dump_err(
                message='No AWS Role was assigned to this application!',
                exit_code=4,
                verbose=self.verbose
            )

        # use the one prvided if there is only one
        if len(idp_role_tuples) == 1:
            role_arn = idp_role_tuples[0][2]
            if self.role_preference and role_arn != self.role_preference:
                Common.echo(
                    message='Your cofigured role was not found; using {role}'.format(
                        role=role_arn
                    )
                )
            else:
                Common.echo(
                    message='Using the configured role {role}'.format(
                        role=role_arn
                    )
                )
            return idp_role_tuples[0]

        # use the configured role if it matches one from the the SAML assertion
        for tup in idp_role_tuples:
            if tup[2] == self.role_preference:
                return tup

        # make the user choose
        return self.__choose_tuple(idp_role_tuples=idp_role_tuples)

    def __discover_role_idp_tuples(self):
        ''' Generate tuples from each possible IDP/Role combination in the SAML assertion '''
        idp_role_pairs = []
        decoded_assertion = base64.b64decode(self.saml_assertion)
        root = ET.fromstring(decoded_assertion)
        for saml2_attribute in root.iter('{urn:oasis:names:tc:SAML:2.0:assertion}Attribute'):
            if saml2_attribute.get('Name') == 'https://aws.amazon.com/SAML/Attributes/Role':
                for saml2_attribute_value in saml2_attribute.iter('{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue'):
                    idp_role_pairs.append(saml2_attribute_value.text)

        idp_role_tuples = []
        for index, pair in enumerate(idp_role_pairs):
            idp_role = pair.split(',')
            tup = (index + 1), idp_role[0], idp_role[1]
            idp_role_tuples.append(tup)

        return idp_role_tuples

    def __choose_tuple(self, idp_role_tuples):
        ''' Give the user a choice from the intersection of configured and supported factors '''
        index = 1
        for tup in idp_role_tuples:
            slashIndex = tup[2].find('/')
            shortName = tup[2][slashIndex+1:] if slashIndex >= 0 else tup[2]
            msg = '{index} - {prompt}'.format(
                index=tup[0],
                prompt=shortName
            )
            Common.echo(message=msg, bold=True)
            index += 1

        raw_choice = None
        try:
            raw_choice = click.prompt('Choose a Role ARN to use', type=int)
            choice = raw_choice - 1
        except ValueError:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.__choose_tuple(idp_role_tuples=idp_role_tuples)

        if len(idp_role_tuples) > choice >= 0:
            pass
        else:
            Common.echo(message='Please select a valid option: you chose: {}'.format(raw_choice))
            return self.__choose_tuple(idp_role_tuples=idp_role_tuples)

        chosen_option = idp_role_tuples[choice]
        if self.verbose:
            Common.dump_verbose(
                message='Using chosen Role {role} & IDP {idp}'.format(
                    role=tup[2],
                    idp=tup[1]
                )
            )

        return chosen_option
