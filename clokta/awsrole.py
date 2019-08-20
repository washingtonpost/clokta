class AwsRole:
    """Represents an AWS role to generate credentials for"""
    def __init__(self, idp_role_str):
        """
        :param idp_role_str: a single comma-separated string with the ARN of the Okta IdP and the ARN of the role
        :type idp_role_str: str
        """
        split_str = idp_role_str.split(',')
        self.idp_arn = split_str[0]
        self.role_arn = split_str[1]
        self.account = self.role_arn.split(':')[4]  # type: str
        self.role_name = self.role_arn.split(':')[5][5:]  # type: str
