import enum


class ConfigParameter:
    """
    This is a structure to hold all the information about a single configured parameter used by Clokta
    (e.g. okta_username)
    """

    class SaveTo(enum.Enum):
        """ Enumeration for to where to save configuration parameter's value """
        DONT_SAVE = 0  # Don't save this parameter anywhere
        DEFAULT = 1  # Save to the default section of the clokta config file
        PROFILE = 2  # Save to the profile section of the clokta config file
        KEYRING = 3  # For passwords.  Save to the OS keyring

    def __init__(self, name, value=None, required=False, save_to=SaveTo.DONT_SAVE,
                 secret=False, default_value=None, prompt=None, param_type=str):
        """
        :param name: the name of the parameter (e.g. okta_username)
        :type name: str
        :param value: the value it has been set to (e.g. doej)
        :type value: str
        :param required: whether this value is required for a clokta login and the user should be
            prompted for a value if none is known.  okta_org is required.  okta_aws_role_to_assume is
            often deduced in the process though may be prompted for later
        :type required: boolean
        :param save_to: where to persistently store this parameters value so we remember it for
            next time.  Options are SAVE_TO_DEFAULT to be stored in the default section of the
            clokta.cfg file, SAVE_TO_PROFILE to be stored in the clokta.cfg file in the section for
            this specific profile, and SAVE_TO_KEYRING for storing passwords
        :type save_to: SaveTo
        :param secret: whether this is a password and should be prompted without echoing
        :type secret: bool
        :param default_value: a default value to use if none is specified
        :type default_value: str or bool
        :param param_type: the type of the parameter.  Usally they are str, but bool is also supported
        :type param_type: type
        :param prompt: the string to use to prompt the user for this parameter
        :type prompt: str
        """
        self.name = name
        self.value = value
        self.required = required
        self.save_to = save_to
        self.secret = secret
        self.default_value = default_value
        self.prompt = prompt
        self.param_type = param_type

